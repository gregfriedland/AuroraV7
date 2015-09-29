#include <uv.h>
#include <iostream>
#include "Util.h"
#include "Camera.h"
#include <fstream>
#include <unistd.h>

Camera::Camera(int width, int height) {
#ifdef RASPICAM
	m_cam.setWidth(width);
  	m_cam.setHeight(height);
	unsigned int n = m_cam.getImageBufferSize();
  	m_imgData = new unsigned char[n];
    m_width = m_cam.getWidth();
    m_height = m_cam.getHeight();
#else
  	m_vc.set(CV_CAP_PROP_FRAME_WIDTH, width);
  	m_vc.set(CV_CAP_PROP_FRAME_HEIGHT, height);
  	m_imgData = new cv::Mat(height, width, CV_8UC3);
    m_width = width;
    m_height = height;
#endif	  	
}

Camera::~Camera() {
	delete m_imgData;
}

int Camera::width() const { 
    return m_cam.getWidth();
}

int Camera::height() const { 
    return m_cam.getHeight(); 
}

void Camera::start(unsigned int interval) {
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

void Camera::stop() {
	std::cout << "Stopping camera.\n";
	uv_timer_stop(&m_timer);
}	

Color24 Camera::pixel(int x, int y) const {
#ifdef RASPICAM
    int index = (x + y * m_width) * 3;
	return Color24(m_imgData[index], 
				   m_imgData[index + 1],
				   m_imgData[index + 2]);
#else
	cv::Vec3b pix = m_imgData->at<cv::Vec3b>(y,x);
	return Color24(pix[0], pix[1], pix[2]);
#endif
}

void Camera::loop() {
	// TODO: make this async
#ifdef RASPICAM		
    m_cam.grab();
    m_cam.retrieve(m_imgData);
#else
    m_vc.grab();
    m_vc.retrieve(*m_imgData);
#endif
}

void Camera::saveImage(string filename) const {
    std::ofstream outFile(filename.c_str(), std::ios::binary);
    outFile<<"P6\n" << m_width << " " << m_height << " 255\n";
    outFile.write ( ( char* ) m_imgData, m_cam.getImageTypeSize ( raspicam::RASPICAM_FORMAT_RGB ) );
    cout<<"Image saved to: " << filename << endl;
}

static void camera_timer_cb(uv_timer_t* handle) {
    ((Camera*)handle->data)->loop();
}
