#include <iostream>
#include "Util.h"
#include "Camera.h"
#include <fstream>
#include <unistd.h>
#include <thread>

// Return the name of the camera backend being used
std::string Camera::backendName() {
#ifdef USE_RASPICAM
    return "raspicam";
#elif defined(USE_LIBCAMERA)
    return "libcamera (GStreamer)";
#else
    return "OpenCV VideoCapture";
#endif
}

#ifdef USE_LIBCAMERA
// Build GStreamer pipeline for libcamera on Pi 5
std::string Camera::buildGStreamerPipeline() const {
    std::stringstream ss;
    // libcamerasrc for Pi 5 camera
    ss << "libcamerasrc ! "
       << "video/x-raw,width=" << m_settings.m_camWidth
       << ",height=" << m_settings.m_camHeight
       << ",framerate=" << static_cast<int>(m_settings.m_fps) << "/1 ! "
       << "videoconvert ! "
       << "appsink";
    return ss.str();
}
#endif

Camera::Camera(const CameraSettings& settings)
: m_fpsCounter(30000, "Camera"), m_settings(settings), m_stop(false) {
#ifdef USE_RASPICAM
    // raspicam uses its own property setting mechanism
    m_cam.set(CV_CAP_PROP_FRAME_WIDTH, m_settings.m_camWidth);
    m_cam.set(CV_CAP_PROP_FRAME_HEIGHT, m_settings.m_camHeight);
    m_cam.set(CV_CAP_PROP_FPS, m_settings.m_fps);
#elif defined(USE_LIBCAMERA)
    // libcamera settings are passed via GStreamer pipeline in init()
#else
    // Standard OpenCV VideoCapture - settings applied after open()
#endif
}

int Camera::camWidth() const {
    return m_settings.m_camWidth;
}

int Camera::camHeight() const {
    return m_settings.m_camHeight;
}

float Camera::fps() const {
    return m_settings.m_fps;
}

void Camera::init() {
    std::cout << "Opening camera using " << backendName() << std::endl;

#ifdef USE_RASPICAM
    // Legacy raspicam for Pi 4 and earlier
    if (!m_cam.open()) {
        std::cerr << "Error opening raspicam" << std::endl;
        return;
    }
#elif defined(USE_LIBCAMERA)
    // libcamera via GStreamer pipeline for Pi 5
    std::string pipeline = buildGStreamerPipeline();
    std::cout << "GStreamer pipeline: " << pipeline << std::endl;
    if (!m_cam.open(pipeline, cv::CAP_GSTREAMER)) {
        std::cerr << "Error opening libcamera via GStreamer" << std::endl;
        std::cerr << "Make sure GStreamer and libcamera are installed:" << std::endl;
        std::cerr << "  sudo apt install gstreamer1.0-tools libgstreamer1.0-dev" << std::endl;
        std::cerr << "  sudo apt install gstreamer1.0-plugins-base gstreamer1.0-plugins-good" << std::endl;

        // Fallback to V4L2 device
        std::cout << "Falling back to V4L2 /dev/video0..." << std::endl;
        if (!m_cam.open(0, cv::CAP_V4L2)) {
            std::cerr << "Error opening camera via V4L2 fallback" << std::endl;
            return;
        }
        // Set properties for V4L2 fallback
        m_cam.set(cv::CAP_PROP_FRAME_WIDTH, m_settings.m_camWidth);
        m_cam.set(cv::CAP_PROP_FRAME_HEIGHT, m_settings.m_camHeight);
        m_cam.set(cv::CAP_PROP_FPS, m_settings.m_fps);
    }
#else
    // Standard OpenCV for desktop/webcam
    if (!m_cam.open(0)) {
        std::cerr << "Error opening camera" << std::endl;
        return;
    }
    m_cam.set(cv::CAP_PROP_FRAME_WIDTH, m_settings.m_camWidth);
    m_cam.set(cv::CAP_PROP_FRAME_HEIGHT, m_settings.m_camHeight);
    m_cam.set(cv::CAP_PROP_FPS, m_settings.m_fps);
#endif

    std::cout << "Camera opened successfully" << std::endl;
}

void Camera::start(unsigned int interval) {
    init();

    m_stop = false;
    auto run = [=]() {
      std::cout << "Starting camera with dims " << m_settings.m_camWidth << "x" << 
        m_settings.m_camHeight << " on thread " << std::this_thread::get_id() << std::endl;

      while (!m_stop) {
            loop(interval);
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        m_stop = false;
    };
    m_thread = std::thread(run);
    m_thread.detach();
}

void Camera::stop() {
    std::cout << "Stopping camera\n";
    m_stop = true;
    if (m_thread.joinable()) {
        m_thread.join();
    }
}   

cv::Mat Camera::getGrayImage() {
    m_mutex.lock();
    auto img = m_grayImg.clone();
    m_mutex.unlock();
    return img;
}

// cv::Mat Camera::getScaledImage() {
//     m_mutex.lock();
//     auto img = m_screenImg.clone();
//     m_mutex.unlock();
//     return img;
// }

void Camera::loop(unsigned int interval) {
    m_frameTimer.tick(interval, [=]() {
        m_fpsCounter.tick();

        m_cam.grab();
        m_cam.retrieve(m_img); // get a new frame from camera

        m_mutex.lock();
        // Use cv::COLOR_BGR2GRAY for OpenCV 4.x compatibility
        cv::cvtColor(m_img, m_grayImg, cv::COLOR_BGR2GRAY);

	auto callback = m_newFrameCallback ? m_newFrameCallback : nullptr;	
        m_mutex.unlock();

        if (callback) {
            callback();
        }
    });
}

void Camera::registerNewFrameCallback(std::function<void()> func) {
    m_mutex.lock();
    m_newFrameCallback = func;
    m_mutex.unlock();
}
