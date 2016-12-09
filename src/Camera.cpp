#include <iostream>
#include "Util.h"
#include "Camera.h"
#include <fstream>
#include <unistd.h>
#include <thread>

#ifndef RAPICAM
  #include <highgui.h>
  #define WINDOW_NAME "Video"
#endif

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
  	m_imgData = cv::Mat(height, width, CV_8UC3);
    m_width = m_imgData.cols;
    m_height = m_imgData.rows;
    cv::namedWindow(WINDOW_NAME, CV_WINDOW_AUTOSIZE);
    cv::moveWindow(WINDOW_NAME, 0, 0);
    std::cout << "Creating video window\n";
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

    std::cout << "Starting camera\n";
    m_stop = false;
    auto run = [=]() {
        while (!m_stop) {
            loop();
            std::this_thread::sleep_for(std::chrono::milliseconds(interval));
        }
        m_stop = false;
    };
    std::thread(run).detach();
}

void Camera::stop() {
	std::cout << "Stopping camera\n";
    m_stop = true;
    while (m_stop) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}	

PixelData Camera::clonePixelData() {
    m_mutex.lock();
    auto pixelData = PixelData(m_width, m_height, m_imgData);
    m_mutex.unlock();
    return pixelData;
}

void Camera::loop() {
    m_fpsCounter.tick();

    // cout << "Camera grab begin...\n";
    m_mutex.lock();
#ifdef RASPICAM		
    m_cam.grab();
    m_cam.retrieve(m_imgData);
#else
    m_vc.grab();
    m_vc.retrieve(m_imgData);
    cv::imshow(WINDOW_NAME, m_imgData);
    cv::waitKey(1);
#endif
    m_mutex.unlock();


    // cout << "Camera grab done.\n";
}
