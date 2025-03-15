#ifndef HZELLER_RPI_MATRIX_H
#define HZELLER_RPI_MATRIX_H

#include "Matrix.h"
#include "led-matrix.h"
#include <iostream>
#include <thread>
#include <mutex>
#include <chrono>
#include <cstdlib>

using namespace rgb_matrix;

class HzellerRpiMatrix : public Matrix {
 public:
    HzellerRpiMatrix(size_t width, size_t height) : Matrix(width, height) {
        RuntimeOptions runtime;
        runtime.gpio_slowdown = 2;

        RGBMatrix::Options options;
        options.hardware_mapping = "regular";
        options.rows = 32;
        options.chain_length = width / 32;
        options.parallel = height / 32;
        options.show_refresh_rate = false;

        m_matrix = CreateMatrixFromOptions(options, runtime);

	// we use 'gamma' correction instead for the desired aesthetic
	if (std::getenv("HZELLER_NO_CORRECTION")) {
  	    std::cout << "Disabling HzellerRpi luminance correction\n";
	    m_matrix->set_luminance_correct(false);
	}
	
        if (m_matrix == NULL) {
          std::cout << "Unable to create hzeller rpi matrix\n";
          exit(1);
        }

	m_offscreenCanvas = m_matrix->CreateFrameCanvas();
    }

    virtual ~HzellerRpiMatrix() {
        delete m_matrix;
    }
  
    virtual void setPixel(size_t x, size_t y, unsigned char r, unsigned char g, unsigned char b) {
      m_offscreenCanvas->SetPixel(x, y, r, g, b);
    }
  
    virtual void update() {   
      m_offscreenCanvas = m_matrix->SwapOnVSync(m_offscreenCanvas, 5);
    }
  
 private:
    RGBMatrix* m_matrix;
    FrameCanvas* m_offscreenCanvas;   
};

#endif
