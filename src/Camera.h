#ifndef CAMERA_H
#define CAMERA_H

#include <iostream>
#include "Util.h"
#include <cstring>
#include <thread>
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/highgui/highgui.hpp>

#ifdef LINUX
    #define RASPICAM
    #include <raspicam_cv.h>
#endif


class Camera {
public:
	Camera(int width, int height);

    int width() const;
    int height() const;

    void init();

    void start(unsigned int interval);

    void stop();

    cv::Mat getGrayImage();

    void loop(unsigned int interval);

private:
    bool m_stop;
    int m_width, m_height;
#ifdef RASPICAM	
    raspicam::RaspiCam_Cv m_cam;
#else
    cv::VideoCapture m_cam;
#endif
    cv::Mat m_img;
    cv::Mat m_lastImg;
    FpsCounter m_fpsCounter;
    FrameTimer m_frameTimer;
    std::thread m_thread;
};

#endif
