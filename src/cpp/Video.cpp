#include "Video.h"
#include <iostream>


VideoDrawer::VideoDrawer(int width, int height, int palSize, Camera* camera) 
: Drawer("Video", width, height, palSize), m_camera(camera), m_colorIndex(0) {
    m_settings.insert(std::make_pair("colorSpeed", 20));
    m_settings.insert(std::make_pair("contrast", 1));
    m_settings.insert(std::make_pair("intermediateResizeFactor", 3));
    m_settings.insert(std::make_pair("medianBlurSize", 1));
    m_settings.insert(std::make_pair("morphOperation", 2));
    m_settings.insert(std::make_pair("morphKernel", 2));
    m_settings.insert(std::make_pair("morphKernelSize", 4));

    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(10,35)));
    m_settingsRanges.insert(std::make_pair("contrast", std::make_pair(1,4)));
    m_settingsRanges.insert(std::make_pair("intermediateResizeFactor", std::make_pair(3, 3)));
    m_settingsRanges.insert(std::make_pair("medianBlurSize", std::make_pair(1, 3)));
    m_settingsRanges.insert(std::make_pair("morphOperation", std::make_pair(-1, 4)));
    m_settingsRanges.insert(std::make_pair("morphKernel", std::make_pair(2,2)));
    m_settingsRanges.insert(std::make_pair("morphKernelSize", std::make_pair(2, 6)));
}

void VideoDrawer::reset() {
    ImageProcSettings s;
    s.m_contrastFactor = m_settings["contrast"];
    s.m_intermediateResizeFactor = m_settings["intermediateResizeFactor"];
    s.m_medianBlurSize = m_settings["medianBlurSize"];
    s.m_morphOperation = m_settings["morphOperation"];
    s.m_morphKernel = m_settings["morphKernel"];
    s.m_morphKernelSize = m_settings["morphKernelSize"];
    m_imageProcSettings = s;
    std::cout << "New image proc settings: " << s.toString() << std::endl;
    
    m_camera->registerNewFrameCallback([=]() {
	cv::Mat img = processImage(m_camera->getGrayImage());
	m_mutex.lock();
	m_screenImg = img;
	m_mutex.unlock();
    });
}

void VideoDrawer::cleanup() {
  m_camera->registerNewFrameCallback(nullptr);
}

void VideoDrawer::draw(int* colIndices) {
    if (m_screenImg.cols == 0 || m_screenImg.rows == 0) {
        std::cout << "Zero sized image from camera\n";
        return;
    }

    m_mutex.lock();
    for (int x = 0; x < m_width; ++x) {
        for (int y = 0; y < m_height; ++y) {
            auto& val = m_screenImg.at<unsigned char>(y, x);
            int index = val * m_palSize / 256 + m_colorIndex;
            colIndices[x + y * m_width] = index;
        }
    }
    m_mutex.unlock();
    
    //m_camera->unlock();
    m_colorIndex += m_settings["colorSpeed"];
}

cv::Mat VideoDrawer::processImage(cv::Mat grayImg) const {    
    cv::Mat screenImg;
    cv::resize(grayImg, screenImg,
        cv::Size(m_imageProcSettings.m_intermediateResizeFactor * m_width,
                 m_imageProcSettings.m_intermediateResizeFactor * m_height));
    cv::medianBlur(screenImg, screenImg, 2 * m_imageProcSettings.m_medianBlurSize + 1); // blur without losing edges
    // cv::GaussianBlur(m_screenImg, m_screenImg, cv::Size(3, 3), 0, 0); // blur

    if (m_imageProcSettings.m_morphOperation >= 0) {
        if (m_imageProcSettings.m_morphOperation > 4) {
            std::cout << "Invalid morph operation\n";
        } else {
            cv::Mat element = cv::getStructuringElement(m_imageProcSettings.m_morphKernel,
            cv::Size(2 * m_imageProcSettings.m_morphKernelSize + 1, 2 * m_imageProcSettings.m_morphKernelSize + 1),
            cv::Size(m_imageProcSettings.m_morphKernelSize, m_imageProcSettings.m_morphKernelSize));
            cv::morphologyEx(screenImg, screenImg, m_imageProcSettings.m_morphOperation + 2, element);
        }
    }
    screenImg.convertTo(screenImg, -1, m_imageProcSettings.m_contrastFactor, 0); // increase contrast
    cv::medianBlur(screenImg, screenImg, 2 * m_imageProcSettings.m_medianBlurSize + 1); // blur without losing edges
    cv::resize(screenImg, screenImg, cv::Size(m_width, m_height));

    return screenImg;
}

VideoDrawer::~VideoDrawer() {}
