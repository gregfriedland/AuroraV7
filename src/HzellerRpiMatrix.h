#ifndef HZELLER_RPI_MATRIX_H
#define HZELLER_RPI_MATRIX_H

#include "Matrix.h"
#include "led-matrix.h"
#include <iostream>
#include <thread>
#include <mutex>
#include <chrono>

using rgb_matrix::RGBMatrix;
using rgb_matrix::Canvas;


void thread_func(size_t width, size_t height, unsigned char* data) {
	RGBMatrix::Options options;
	rgb_matrix::RuntimeOptions runtime;

	options.hardware_mapping = "regular";
	options.rows = 32;
	options.chain_length = width / 32;
	options.parallel = height / 32;
	options.show_refresh_rate = true;
	auto canvas = rgb_matrix::CreateMatrixFromOptions(options, runtime);
	if (canvas == NULL) {
		std::cout << "Unable to create hzeller rpi matrix\n";
		exit(1);
	}

	std::chrono::milliseconds sleepMs{1};
	while (true) {
		for (size_t x = 0; x < width; ++x) {
			for (size_t y = 0; y < height; ++y) {
				size_t index = y * width * 3 + x * 3;
				canvas->SetPixel(x, y, data[index], data[index + 1], data[index + 2]);
			}
		}
		std::this_thread::sleep_for(sleepMs);
	}

	delete canvas;
}

class HzellerRpiMatrix : public Matrix {
 public:
	HzellerRpiMatrix(size_t width, size_t height) : Matrix(width, height) {
		m_data = new unsigned char[width * height * 3];
		std::thread t(&thread_func, width, height, m_data);
	}

	virtual ~HzellerRpiMatrix() {
		delete [] m_data;
	}

	virtual void setPixel(size_t x, size_t y, char r, char g, char b) {
		m_data[y * m_width * 3 + x * 3] = r;
		m_data[y * m_width * 3 + x * 3 + 1] = g;
		m_data[y * m_width * 3 + x * 3 + 2] = b;
		// m_canvas->SetPixel(x, y, r, g, b);
	}

	virtual void update() {	
	}

	virtual const unsigned char* rawData(size_t& size) const {
		std::cout << "HzellerRpiMatrix rawData() not implemented\n";
		exit(1);
		return nullptr;
	}

 private:
	unsigned char* m_data;
};

#endif
