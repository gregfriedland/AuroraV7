#ifndef FACEDETECT_H
#define FACEDETECT_H

#include <opencv2/opencv.hpp>
#include <opencv2/objdetect/objdetect.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <opencv2/imgproc/imgproc.hpp>

#include <uv.h>
#include <iostream>
#include <vector>

static void facedetect_timer_cb(uv_timer_t* handle);

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

private:
    void loop();

    Camera* m_camera;
    cv::CascadeClassifier m_faceCascade;
    cv::Mat *m_image;
    uv_timer_t m_timer;
    bool m_status;
};

inline static void facedetect_timer_cb(uv_timer_t* handle) {
    ((FaceDetect*)handle->data)->loop();
}




 

#endif
