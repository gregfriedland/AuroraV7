#ifndef COMPUTER_SCREEN_MATRIX_H
#define COMPUTER_SCREEN_MATRIX_H

#include "Matrix.h"
#include <iostream>
#include <highgui.h>
#include <iostream>

#define WINDOW_NAME "Aurora"
#define MIN_WINDOW_WIDTH 1280

class ComputerScreenMatrix : public Matrix {
 public:
	ComputerScreenMatrix(size_t width, size_t height) : Matrix(width, height) {
		m_pixelMultiplier = std::ceil((float)MIN_WINDOW_WIDTH / width);

        std::cout << "Creating video window\n";
        cv::namedWindow(WINDOW_NAME, CV_WINDOW_AUTOSIZE);
	    m_img = cv::Mat(height * m_pixelMultiplier, width * m_pixelMultiplier, CV_8UC3);
        cv::imshow(WINDOW_NAME, m_img);
        cv::waitKey(1);            
	}

	virtual void setPixel(size_t x, size_t y, unsigned char r, unsigned char g, unsigned char b) {
        int m = m_pixelMultiplier;
        for (int xx = 0; xx < m; ++xx) {
            for (int yy = 0; yy < m; ++yy) {
		        cv::Vec3b& pix = m_img.at<cv::Vec3b>(y * m + yy, x * m + xx);
		        pix[0] = r;
		        pix[1] = g;
		        pix[2] = b;
		    }
		}
    }

	virtual void update() {	
        cv::imshow(WINDOW_NAME, m_img);
        cv::waitKey(1);            
	}

 private:
 	cv::Mat m_img;
 	size_t m_pixelMultiplier;
};

#endif
