#include <iostream>
#include "Util.h"
#include "Camera.h"
#include <fstream>
#include <unistd.h>
#include <thread>

Camera::Camera(int width, int height)
 : m_fpsCounter(30000, "Camera") {
    m_cam.set(CV_CAP_PROP_FORMAT, CV_8UC3);

    m_cam.set(CV_CAP_PROP_FRAME_WIDTH, width);
    m_cam.set(CV_CAP_PROP_FRAME_HEIGHT, height);
    // m_img = cv::Mat(height, width, CV_8UC3);

    // m_cam.read(m_img);
    m_width = width;
    m_height = height;
    // m_width = m_vc.get(CV_CAP_PROP_FRAME_WIDTH);
    // m_height = m_vc.get(CV_CAP_PROP_FRAME_HEIGHT);

    std::cout << "Creating camera with dims " << m_width << "x" << m_height <<
        " (desired " << width << "x" << height << ")\n";
}

int Camera::width() const { 
    return m_width;
}

int Camera::height() const { 
    return m_height;
}

void Camera::init() {
#ifdef RASPICAM
  if (!m_cam.open()) {
#else
  if (!m_cam.open(0)) {
#endif
        std::cerr << "Error opening camera" << std::endl;
        return;
    }
}

void Camera::start(unsigned int interval) {
    init();

    std::cout << "Starting camera with dims " << m_width << "x" << m_height << "\n";
    m_stop = false;
    auto run = [=]() {
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
    // m_mutex.lock();
    return m_lastImg;
    // m_imgData
    // auto pixelData = PixelData(m_width, m_height, m_imgData);
    // m_mutex.unlock();
    // return img;
}

void Camera::loop(unsigned int interval) {
    m_frameTimer.tick(interval, [=]() {
        m_fpsCounter.tick();

        m_cam.grab();
	m_cam.retrieve(m_img); // get a new frame from camera
	cv::cvtColor(m_img, m_lastImg, CV_BGR2GRAY);
    });
}
