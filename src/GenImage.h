#ifndef GENIMAGE_H
#define GENIMAGE_H

#include <string>
#include <uv.h>

using std::string;

static void genimage_timer_cb(uv_timer_t* handle);

class GenImage {
public:
	GenImage(int width, int height, string outFilename, const unsigned char* srcData);

	void start(unsigned int interval);

	void stop();

    friend void genimage_timer_cb(uv_timer_t* handle);

private:
	void loop();

	int m_width, m_height;
	string m_outFilename;
	const unsigned char* m_srcData;
    uv_timer_t m_timer;
};

#endif