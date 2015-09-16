#include <lodepng.h>
#include <string>
#include <iostream>
#include <uv.h>

static void genimage_timer_cb(uv_timer_t* handle);

class GenImage {
public:
	GenImage(int width, int height, string outFilename, const unsigned char* srcData)
	: m_width(width), m_height(height), m_outFilename(outFilename), m_srcData(srcData)
	{}

	void start(unsigned int interval) {
		uv_timer_init(uv_default_loop(), &m_timer);
		m_timer.data = this;
		uv_timer_start(&m_timer, genimage_timer_cb, 0, interval);
		std::cout << "Starting GenImage timer\n";
	}

	void stop() {
		uv_timer_stop(&m_timer);
	}

    friend void genimage_timer_cb(uv_timer_t* handle);

private:
	void loop() {
		//std::cout << "writing image to: " << m_outFilename << std::endl;
		lodepng_encode24_file(m_outFilename.c_str(), m_srcData, m_width, m_height);

		static int count = 0;
		if (count++ > 200)
			exit(0);
	}

	int m_width, m_height;
	string m_outFilename;
	const unsigned char* m_srcData;
    uv_timer_t m_timer;
};

inline static void genimage_timer_cb(uv_timer_t* handle) {
    ((GenImage*)handle->data)->loop();
}
