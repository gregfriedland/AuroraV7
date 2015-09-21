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


static void facedetect_timer_cb(uv_timer_t* handle);
static void facedetect_async(uv_work_t *work);

class FaceDetect {
public:
    FaceDetect(Camera* camera);

    ~FaceDetect();

	void start(unsigned int interval);

	void stop();

    bool status();

    friend void facedetect_timer_cb(uv_timer_t* handle);
    friend void facedetect_async(uv_work_t* work);

private:
    void loop();

    Camera* m_camera;
    cv::CascadeClassifier m_faceCascade;
    cv::Mat *m_image;
    uv_timer_t m_timer; // for scheduling callbacks at regulat intervals
    uv_work_t m_work;   // for doing in a separate thread
    bool m_status;
};


#endif
