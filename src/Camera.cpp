#include <iostream>
#include "Util.h"
#include "Camera.h"
#include <fstream>
#include <unistd.h>
#include <thread>

Camera::Camera(int camWidth, int camHeight, int screenWidth, int screenHeight)
: m_fpsCounter(30000, "Camera"), m_camWidth(camWidth), m_camHeight(camHeight),
  m_screenWidth(screenWidth), m_screenHeight(screenHeight) {
    m_cam.set(CV_CAP_PROP_FORMAT, CV_8UC3);

    m_cam.set(CV_CAP_PROP_FRAME_WIDTH, camWidth);
    m_cam.set(CV_CAP_PROP_FRAME_HEIGHT, camHeight);
}

int Camera::camWidth() const { 
    return m_camWidth;
}

int Camera::camHeight() const { 
    return m_camHeight;
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

    std::cout << "Starting camera with dims " << m_camWidth << "x" << m_camHeight << "\n";
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
    m_mutex.lock();
    auto img = m_grayImg.clone();
    m_mutex.unlock();
    return img;
}

cv::Mat Camera::getScaledImage() {
    m_mutex.lock();
    auto img = m_screenImg.clone();
    m_mutex.unlock();
    return img;
}

void Camera::loop(unsigned int interval) {
    m_frameTimer.tick(interval, [=]() {
        m_fpsCounter.tick();

        m_cam.grab();
	m_cam.retrieve(m_img); // get a new frame from camera

	m_mutex.lock();
	cv::cvtColor(m_img, m_grayImg, CV_BGR2GRAY);
	cv::resize(m_grayImg, m_screenImg, cv::Size(m_screenWidth, m_screenHeight));
	//cv::GaussianBlur(m_screenImg, m_screenImg, cv::Size(3, 3), 0, 0);
	m_screenImg.convertTo(m_screenImg, -1, 2.5, -50);
	
	m_mutex.unlock();
    });
}
