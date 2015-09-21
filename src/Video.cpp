#include "Video.h"
#include <iostream>

VideoDrawer::VideoDrawer(int width, int height, int palSize, const Camera* camera) 
: Drawer("Video", width, height, palSize), m_camera(camera), m_colorIndex(0) {
    m_settings.insert(make_pair("colorSpeed",0));
    m_settingsRanges.insert(make_pair("colorSpeed", make_pair(0,50)));
}

void VideoDrawer::reset() {
}

void VideoDrawer::draw(int* colIndices) {
	for (int x=0; x<m_width; x++) {
		int xx = x * m_camera->width() / m_width;
		for (int y=0; y<m_height; y++) {
		    int yy = y * m_camera->height() / m_height;
		    Color24 col = m_camera->pixel(xx, yy);
		    int gray = (col.r + col.g + col.b) / 3;
		    int index = gray * m_palSize / 256 + m_colorIndex;
        	colIndices[x + y * m_width] = index;
        }
    }
    m_colorIndex += m_settings["colorSpeed"];
}

VideoDrawer::~VideoDrawer() {}
