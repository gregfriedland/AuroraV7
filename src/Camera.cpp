#include <iostream>
#include "Util.h"
#include "Camera.h"
#include <fstream>
#include <unistd.h>
#include <thread>

Camera::Camera(int width, int height)
 : m_fpsCounter(5000, "Camera") {
#ifdef RASPICAM
	m_cam.setWidth(width);
  	m_cam.setHeight(height);
	unsigned int n = m_cam.getImageBufferSize();
  	m_imgData = new unsigned char[n];
    m_width = m_cam.getWidth();
    m_height = m_cam.getHeight();
#else
    m_vc.set(CV_CAP_PROP_FRAME_WIDTH, width);
    m_vc.set(CV_CAP_PROP_FRAME_HEIGHT, height);
    // m_img = cv::Mat(height, width, CV_8UC3);

    m_vc.read(m_img);
    m_width = width;
    m_height = height;
    // m_width = m_vc.get(CV_CAP_PROP_FRAME_WIDTH);
    // m_height = m_vc.get(CV_CAP_PROP_FRAME_HEIGHT);

    std::cout << "Creating camera with dims " << m_width << "x" << m_height <<
        " (desired " << width << "x" << height << ")\n";
#endif	  	
}

Camera::~Camera() {
#ifdef LINUX
    delete[] m_imgData;
#endif
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
    if (!m_vc.open(0)) {
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
    return m_grayImg;
    // m_imgData
    // auto pixelData = PixelData(m_width, m_height, m_imgData);
    // m_mutex.unlock();
    // return img;
}

void Camera::loop(unsigned int interval) {
    m_frameTimer.tick(interval, [=]() {
        m_fpsCounter.tick();

#ifdef RASPICAM		
        m_mutex.lock();
        m_cam.grab();
        m_cam.retrieve(m_imgData);
        m_mutex.unlock();
#else
        // m_mutex.lock();
        m_vc >> m_img; // get a new frame from camera
        cvtColor(m_img, m_grayImg, CV_BGR2GRAY);
        // m_vc.grab();
        // m_vc.retrieve(m_img);
        // // m_mutex.unlock();
#endif
    });
}
