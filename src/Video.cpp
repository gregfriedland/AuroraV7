#include "Video.h"
#include <iostream>

using namespace std;

VideoDrawer::VideoDrawer(int width, int height, int palSize, Camera* camera) 
: Drawer("Video", width, height, palSize), m_camera(camera), m_colorIndex(0) {
    m_settings.insert(make_pair("colorSpeed", 20));
    m_settings.insert(make_pair("contrast", 5));
    m_settings.insert(make_pair("intermediateResizeFactor", 3));
    m_settings.insert(make_pair("medianBlurSize", 2));
    m_settings.insert(make_pair("morphOperation", 4));
    m_settings.insert(make_pair("morphKernel", 2));
    m_settings.insert(make_pair("morphKernelSize", 10));

    m_settingsRanges.insert(make_pair("colorSpeed", make_pair(10,35)));
    m_settingsRanges.insert(make_pair("contrast", make_pair(1,4)));
    m_settingsRanges.insert(make_pair("intermediateResizeFactor", make_pair(3, 3)));
    m_settingsRanges.insert(make_pair("medianBlurSize", make_pair(1, 3)));
    m_settingsRanges.insert(make_pair("morphOperation", make_pair(-1, 4)));
    m_settingsRanges.insert(make_pair("morphKernel", make_pair(2,2)));
    m_settingsRanges.insert(make_pair("morphKernelSize", make_pair(2, 6)));
}

void VideoDrawer::reset() {
    ImageProcSettings s;
    s.m_contrastFactor = m_settings["contrast"];
    s.m_intermediateResizeFactor = m_settings["intermediateResizeFactor"];
    s.m_medianBlurSize = m_settings["medianBlurSize"];
    s.m_morphOperation = m_settings["morphOperation"];
    s.m_morphKernel = m_settings["morphKernel"];
    s.m_morphKernelSize = m_settings["morphKernelSize"];
    m_camera->setImageProcSettings(s);
}

void VideoDrawer::draw(int* colIndices) {
  m_camera->lock();
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
    m_camera->unlock();
    m_colorIndex += m_settings["colorSpeed"];
}

VideoDrawer::~VideoDrawer() {}
