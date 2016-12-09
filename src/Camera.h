#ifndef CAMERA_H
#define CAMERA_H

#include <iostream>
#include "Util.h"
#include <mutex>
#include <cstring>

#ifdef LINUX
	#define RASPICAM
	#include <raspicam/raspicam.h>
    typedef unsigned char* ImageData;
#else
	#include <opencv2/imgproc/imgproc.hpp>
	#include <opencv2/highgui/highgui.hpp>
    typedef cv::Mat ImageData;
#endif

class PixelData {
 public:
    PixelData(int width, int height, ImageData imgData) {
        m_width = width;
        m_height = height;

#ifdef LINUX
        m_imgData = new unsigned char[width * height * 3];
        //        std::cout << "copying " << (width * height * 3) << " bytes of image data\n";
        std::memcpy(m_imgData, imgData, width * height * 3);
#else
        m_imgData = imgData.clone();
#endif
    }

    Color24 get(int x, int y) const {
#ifdef RASPICAM
    int index = (x + y * m_width) * 3;
    return Color24(m_imgData[index], 
                   m_imgData[index + 1],
                   m_imgData[index + 2]);
#else
    // cout << x << " " << y << endl;
    cv::Vec3b pix = m_imgData.at<cv::Vec3b>(y,x);
    // cout << (int)pix[0] << " " << (int)pix[1] << " " << (int)pix[2] << endl; 
    return Color24(pix[0], pix[1], pix[2]);
#endif
    }

    ~PixelData() {
#ifdef LINUX
        delete[] m_imgData;
#endif
    }

    double mean() const {
        double total = 0;
        for (int x = 0; x < m_width; ++x) {
            for (int y = 0; y < m_height; ++y) {
                auto col = get(x, y);
                total += col.r + col.g + col.b;
            }
        }
        return total / (m_width * m_height * 3);
    }

 private:
    int m_width, m_height;
    ImageData m_imgData;
};


class Camera {
public:
	Camera(int width, int height);

	~Camera();

    int width() const;
    int height() const;

    void init();

	void start(unsigned int interval);

	void stop();

	PixelData clonePixelData();

	void loop();

private:
    bool m_stop;
	int m_width, m_height;
#ifdef RASPICAM	
	raspicam::RaspiCam m_cam;
#else
	cv::VideoCapture m_vc;
#endif
    ImageData m_imgData;
    std::mutex m_mutex;
    FpsCounter m_fpsCounter;
};

#endif
