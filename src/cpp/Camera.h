#ifndef CAMERA_H
#define CAMERA_H

#include <iostream>
#include "Util.h"
#include <cstring>
#include <thread>
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <mutex>
#include <sstream>

#ifdef __arm__
    #include <raspicam_cv.h>
#endif

struct CameraSettings {
    int m_camWidth, m_camHeight, m_screenWidth, m_screenHeight;
    float m_fps;
};

struct ImageProcSettings {
    float m_contrastFactor;
    int m_intermediateResizeFactor;
    int m_medianBlurSize;
    int m_morphOperation;
    int m_morphKernel;
    int m_morphKernelSize;

    std::string toString() const {
        std::stringstream ss;
        ss << "contrast=" << m_contrastFactor << " intResizeFactor=" << m_intermediateResizeFactor <<
            " medianBlurSize=" << m_medianBlurSize << " morphOp=" << m_morphOperation <<
            " morphKernel=" << m_morphKernel << "(size=" << m_morphKernelSize << ")";
        return ss.str();
    }
};

class Camera {
public:
    Camera(const CameraSettings& settings);

    int camWidth() const;
    int camHeight() const;
    float fps() const;

    void init();

    void start(unsigned int interval);

    void stop();
    cv::Mat getGrayImage();

    void loop(unsigned int interval);

    void registerNewFrameCallback(std::function<void()> func);

private:
    bool m_stop;
    CameraSettings m_settings;
#ifdef __arm__	
    raspicam::RaspiCam_Cv m_cam;
#else
    cv::VideoCapture m_cam;
#endif
    cv::Mat m_img, m_grayImg;
    FpsCounter m_fpsCounter;
    FrameTimer m_frameTimer;
    std::thread m_thread;
    std::mutex m_mutex;
    ImageProcSettings m_imageProcSettings;
    std::function<void()> m_newFrameCallback;
};

#endif
