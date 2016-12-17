#ifndef FACEDETECT_H
#define FACEDETECT_H

#include <opencv2/opencv.hpp>
#include <opencv2/objdetect/objdetect.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <opencv2/imgproc/imgproc.hpp>

#include <iostream>
#include <vector>
#include <thread>

#include "Camera.h"


class FaceDetect {
public:
    FaceDetect(Camera* camera);

    ~FaceDetect();

	void start(unsigned int interval);

	void stop();

    unsigned long lastDetection();

    void loop(unsigned int interval);

private:
    Camera* m_camera;
    cv::CascadeClassifier m_faceCascade;
    unsigned long m_lastDetection;
    bool m_stop;
    FpsCounter m_fpsCounter;
    FrameTimer m_frameTimer;
    std::thread m_thread;
};


#endif
