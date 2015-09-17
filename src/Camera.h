#ifndef CAMERA_H
#define CAMERA_H

#include <uv.h>
#include <iostream>
#include "Util.h"

#ifdef LINUX
	#define RASPICAM
	#include <raspicam.h>
#else
	#include <opencv2/imgproc/imgproc.hpp>
	#include <opencv2/highgui/highgui.hpp>
#endif


static void camera_timer_cb(uv_timer_t* handle);

class Camera {
public:
	Camera(int width, int height) : m_width(width), m_height(height) {
#ifdef RASPICAM
		m_cam.setWidth(width);
	  	m_cam.setHeight(height);
		unsigned int n = m_cam.getImageBufferSize();
	  	m_imgData = new unsigned char[n];
#else
	  	m_vc.set(CV_CAP_PROP_FRAME_WIDTH, width);
	  	m_vc.set(CV_CAP_PROP_FRAME_HEIGHT, height);
	  	m_imgData = new cv::Mat(height, width, CV_8UC3);
#endif	  	
	}

	~Camera() {
		delete m_imgData;
	}

    int width() const { return m_width; }
    int height() const { return m_height; }

	void start(unsigned int interval) {
#ifdef RASPICAM
		if (!m_cam.open()) {
#else    
		if (m_vc.open(0)) {
#endif			
		    std::cerr << "Error opening camera" << std::endl;
		} else {
			uv_timer_init(uv_default_loop(), &m_timer);
			m_timer.data = this;
			uv_timer_start(&m_timer, camera_timer_cb, 0, interval);
			std::cout << "Starting camera\n";
		}
	}

	void stop() {
		std::cout << "Stopping camera\n";
		uv_timer_stop(&m_timer);
	}	

	Color24 pixel(int x, int y) const {
#ifdef RASPICAM
		return Color24(m_imgData[x + y * m_width], 
					   m_imgData[x + y * m_width + 1],
					   m_imgData[x + y * m_width + 2]);
#else
		cv::Vec3b pix = m_imgData->at<cv::Vec3b>(y,x);
		return Color24(pix[0], pix[1], pix[2]);
#endif
	}

    friend void camera_timer_cb(uv_timer_t* handle);

private:
	void loop() {
		// TODO: make this async
#ifdef RASPICAM		
	    m_cam.grab();
	    m_cam.retrieve(m_imgData);
#else
	    m_vc.grab();
	    m_vc.retrieve(*m_imgData);
#endif

	}

	int m_width, m_height;
#ifdef RASPICAM	
	raspicam::RaspiCam m_cam;
	unsigned char *m_imgData;
#else
	cv::VideoCapture m_vc;
	cv::Mat *m_imgData;
#endif


    uv_timer_t m_timer;
};

inline static void camera_timer_cb(uv_timer_t* handle) {
    ((Camera*)handle->data)->loop();
}

#endif
