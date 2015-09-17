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
    FaceDetect(Camera* camera) : m_camera(camera), m_status(false) {
        m_image = new cv::Mat(camera->height(), camera->width(), CV_8UC1);
        m_faceCascade.load("src/haarcascade_frontalface_alt2.xml");
    }

    ~FaceDetect() {
        delete m_image;
    }

	void start(unsigned int interval) {
        m_work.data = this;
        uv_timer_init(uv_default_loop(), &m_timer);
        m_timer.data = this;
        uv_timer_start(&m_timer, facedetect_timer_cb, 0, interval);
        std::cout << "Starting face detection\n";
	}

	void stop() {
		std::cout << "Stopping face detection\n";
		uv_timer_stop(&m_timer);
	}	

    bool status() { return m_status; }

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

inline static void facedetect_timer_cb(uv_timer_t* handle) {
    uv_work_t *work = &((FaceDetect*)handle->data)->m_work;
    uv_queue_work(uv_default_loop(), work, facedetect_async, NULL);
}

inline static void facedetect_async(uv_work_t* work) {
    ((FaceDetect*)work->data)->loop();
}

#endif
