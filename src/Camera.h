#ifndef CAMERA_H
#define CAMERA_H

#include <uv.h>
#include <iostream>
#include "Util.h"

#ifdef LINUX
	#define RASPICAM
	#include <raspicam.h>
#endif


static void camera_timer_cb(uv_timer_t* handle);

class Camera {
public:
	Camera(int width, int height) : m_width(width), m_height(height) {
		m_cam.setWidth(width);
	  	m_cam.setHeight(height);
		unsigned int n = m_cam.getImageBufferSize();
	  	m_imgData = new unsigned char[n];
	}

	~Camera() {
		delete m_imgData;
	}

    int width() const { return m_width; }
    int height() const { return m_height; }

	void start(unsigned int interval) {
		if ( !m_cam.open() ) {
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
		return Color24(m_imgData[x + y * m_width], 
					m_imgData[x + y * m_width + 1],
					m_imgData[x + y * m_width + 2]);
	}

    friend void camera_timer_cb(uv_timer_t* handle);

private:
	void loop() {
		// TODO: make this async
	    m_cam.grab();
	    m_cam.retrieve(m_imgData);
	}

	int m_width, m_height;
	raspicam::RaspiCam m_cam;
	unsigned char *m_imgData;

    uv_timer_t m_timer;
};

inline static void camera_timer_cb(uv_timer_t* handle) {
    ((Camera*)handle->data)->loop();
}

#endif
