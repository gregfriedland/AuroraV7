#ifndef HZELLER_RPI_MATRIX_H
#define HZELLER_RPI_MATRIX_H

#include "Matrix.h"
#include "led-matrix.h"
#include <iostream>

using rgb_matrix::RGBMatrix;
using rgb_matrix::Canvas;

class HzellerRpiMatrix : public Matrix {
 public:
	HzellerRpiMatrix(size_t width, size_t height) : Matrix(width, height) {
		RGBMatrix::Options options;
		rgb_matrix::RuntimeOptions runtime;

		options.hardware_mapping = "regular";
		options.rows = 32;
		options.chain_length = width / 32;
		options.parallel = height / 32;
		options.show_refresh_rate = true;
		m_canvas = rgb_matrix::CreateMatrixFromOptions(options, runtime);
		if (m_canvas == NULL) {
			std::cout << "Unable to create hzeller rpi matrix\n";
			exit(1);
		}
	}

	virtual ~HzellerRpiMatrix() {
		delete m_canvas;
	}

	virtual void setPixel(size_t x, size_t y, char r, char g, char b) {
		m_canvas->SetPixel(x, y, r, g, b);
	}

	virtual void update() {	
	}

	virtual const unsigned char* rawData(size_t& size) const {
		std::cout << "Not implemented\n";
		exit(1);
		return nullptr;
	}

 private:
  	Canvas* m_canvas;
};

#endif
