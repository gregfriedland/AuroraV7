#include <lodepng.h>
#include <string>
#include <iostream>
#include <uv.h>
#include "GenImage.h"

GenImage::GenImage(int width, int height, string outFilename, const unsigned char* srcData)
: m_width(width), m_height(height), m_outFilename(outFilename), m_srcData(srcData)
{}

void GenImage::start(unsigned int interval) {
	uv_timer_init(uv_default_loop(), &m_timer);
	m_timer.data = this;
	uv_timer_start(&m_timer, genimage_timer_cb, 0, interval);
	std::cout << "Starting GenImage timer\n";
}

void GenImage::stop() {
	uv_timer_stop(&m_timer);
}

void GenImage::loop() {
	//std::cout << "writing image to: " << m_outFilename << std::endl;
	lodepng_encode24_file(m_outFilename.c_str(), m_srcData, m_width, m_height);

	static int count = 0;
	if (count++ > 200)
		exit(0);
}

static void genimage_timer_cb(uv_timer_t* handle) {
    ((GenImage*)handle->data)->loop();
}
