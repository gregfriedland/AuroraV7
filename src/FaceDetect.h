#ifndef FACEDETECT_H
#define FACEDETECT_H

#include <opencv2/opencv.hpp>
#include <opencv2/objdetect/objdetect.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <opencv2/imgproc/imgproc.hpp>

#include <uv.h>
#include <iostream>
#include <vector>

#include "Camera.h"

using namespace std;


class FaceDetect {
public:
    FaceDetect(Camera* camera);

    ~FaceDetect();

	void start(unsigned int interval);

	void stop();

    bool status();

    void loop();

private:
    Camera* m_camera;
    cv::CascadeClassifier m_faceCascade;
    cv::Mat *m_image;
    uv_timer_t m_timer; // for scheduling callbacks at regulat intervals
    bool m_status;
};


#endif
