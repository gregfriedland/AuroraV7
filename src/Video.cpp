#include "Video.h"
#include <iostream>

using namespace std;

VideoDrawer::VideoDrawer(int width, int height, int palSize, Camera* camera) 
: Drawer("Video", width, height, palSize), m_camera(camera), m_colorIndex(0) {
    m_settings.insert(make_pair("colorSpeed",20));
    m_settingsRanges.insert(make_pair("colorSpeed", make_pair(10,50)));
}

void VideoDrawer::reset() {
}

void VideoDrawer::draw(int* colIndices) {
    auto img = m_camera->getScaledImage();
    if (img.cols == 0 || img.rows == 0) {
      std::cout << "Zero sized image from camera\n";
      return;
    }
    for (int x = 0; x < m_width; ++x) {
        for (int y = 0; y < m_height; ++y) {
  	    auto& val = img.at<unsigned char>(y, x);
	    int index = val * m_palSize / 256 + m_colorIndex;
	    colIndices[x + y * m_width] = index;
        }
    }
    m_colorIndex += m_settings["colorSpeed"];
}

VideoDrawer::~VideoDrawer() {}
