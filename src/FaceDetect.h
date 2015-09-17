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
        m_image = new cv::Mat(camera->height(), camera->width(), CV_8UC3);
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
	void loop() {
        for (int x = 0; x < m_camera->width(); x++)
            for (int y = 0; y < m_camera->height(); y++) {
                Color24 col = m_camera->pixel(x, y);
                m_image->at<cv::Vec3b>(y,x) = cv::Vec3b(col.r, col.g, col.b);
            }

		// TODO: make this async
        std::vector<cv::Rect> faces;
        cout << "Detecting faces...\n";
        m_faceCascade.detectMultiScale(*m_image, faces, 1.2, 2,
                                       0|CV_HAAR_SCALE_IMAGE, cv::Size(20, 20), cv::Size(200, 200)); 
        cout << "done\n";
        m_status = faces.size() > 0;
        if (m_status)
            cout << "Detected " << faces.size() << " faces\n";
	}

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
