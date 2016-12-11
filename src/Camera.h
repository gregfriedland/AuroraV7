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

struct CameraSettings {
    int m_camWidth, m_camHeight, m_screenWidth, m_screenHeight;
    float m_fps;
    float m_contrastFactor;
    int m_intermediateResizeFactor;
    int m_medianBlurSize;
    int m_morphOperationType;
    int m_morphKernelType;
    int m_morphKernelSize;
};

class Camera {
public:
    Camera(const CameraSettings& settings);

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
    CameraSettings m_settings;
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
