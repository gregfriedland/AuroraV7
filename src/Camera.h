#ifndef CAMERA_H
#define CAMERA_H

#include <iostream>
#include "Util.h"
#include <cstring>
#include <thread>
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <mutex>

#ifdef LINUX
    #define RASPICAM
    #include <raspicam_cv.h>
#endif


class Camera {
public:
    Camera(int camWidth, int camHeight, int screenWidth, int screenHeight);

    int camWidth() const;
    int camHeight() const;

    void init();

    void start(unsigned int interval);

    void stop();

    cv::Mat getGrayImage();
    cv::Mat getScaledImage();

    void loop(unsigned int interval);

private:
    bool m_stop;
    int m_camWidth, m_camHeight, m_screenWidth, m_screenHeight;
#ifdef RASPICAM	
    raspicam::RaspiCam_Cv m_cam;
#else
    cv::VideoCapture m_cam;
#endif
    cv::Mat m_img, m_grayImg, m_screenImg;
    FpsCounter m_fpsCounter;
    FrameTimer m_frameTimer;
    std::thread m_thread;
    std::mutex m_mutex;
};

#endif
