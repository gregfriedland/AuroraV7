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
	Camera(int width, int height);

	~Camera();

    int width() const;
    int height() const;

	void start(unsigned int interval);

	void stop();

	Color24 pixel(int x, int y) const;

    void saveImage(string filename) const;

    friend void camera_timer_cb(uv_timer_t* handle);

private:
	void loop();

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

#endif
