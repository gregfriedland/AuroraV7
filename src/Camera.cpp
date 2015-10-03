#include <uv.h>
#include <iostream>
#include "Util.h"
#include "Camera.h"
#include <fstream>
#include <unistd.h>

Camera::Camera(int width, int height)
: m_grabbing(false), m_lastMean(0), m_currMean(0) {
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
    m_width = m_imgData->cols;
    m_height = m_imgData->rows;
#endif	  	
}

Camera::~Camera() {
	delete m_imgData;
}

int Camera::width() const { 
    return m_width;
}

int Camera::height() const { 
    return m_height;
}

void Camera::start(unsigned int interval) {
#ifdef RASPICAM
	if (!m_cam.open()) {
#else    
	if (!m_vc.open(0)) {
#endif			
	    std::cerr << "Error opening camera" << std::endl;
	} else {
        m_work.data = this;
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
    // cout << x << " " << y << endl;
	cv::Vec3b pix = m_imgData->at<cv::Vec3b>(y,x);
    // cout << (int)pix[0] << " " << (int)pix[1] << " " << (int)pix[2] << endl; 
	return Color24(pix[0], pix[1], pix[2]);
#endif
}

void Camera::loop() {
    if (m_grabbing)
        return;
    m_grabbing = true;

    m_lastMean = m_currMean;

    // cout << "Camera grab begin...\n";
#ifdef RASPICAM		
    m_cam.grab();
    //m_imgData = m_cam.getImageBufferData();
    m_cam.retrieve(m_imgData);
#else
    m_vc.grab();
    // m_vc.retrieve(*m_imgData);
#endif
    // cout << "Camera grab done.\n";

    m_currMean = mean();
    //cout << "camera diff: " << diff() << endl;
    m_grabbing = false;
}

void Camera::saveImage(string filename) const {
    std::ofstream outFile(filename.c_str(), std::ios::binary);
    outFile<<"P6\n" << m_width << " " << m_height << " 255\n";
#ifdef RASPICAM
    outFile.write ( ( char* ) m_imgData, m_cam.getImageTypeSize ( raspicam::RASPICAM_FORMAT_RGB ) );
    cout<<"Image saved to: " << filename << endl;
#endif    
}

double Camera::mean() const {
#ifdef RASPICAM
    double total = 0;
    for (int i = 0; i < m_width * m_height * 3; i++)
        total += m_imgData[i];
#else
    double total = 0;
    for (int i = 0; i < m_width * m_height; i++) {
        cv::Vec3b rgb = m_imgData->at<cv::Vec3b>(i); 
        total += rgb[0] + rgb[1] + rgb[2];
    }
#endif    
    return total / (m_width * m_height * 3);
}

double Camera::diff() const {
    return max(min(abs(m_currMean - m_lastMean), 1.0), 0.0);
}

static void camera_timer_cb(uv_timer_t* handle) {
    uv_work_t *work = &((Camera*)handle->data)->m_work;
    uv_queue_work(uv_default_loop(), work, camera_async, NULL);
}

 static void camera_async(uv_work_t* work) {
     ((Camera*)work->data)->loop();
 }
