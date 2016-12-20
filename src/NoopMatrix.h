#ifndef NOOP_MATRIX_H
#define NOOP_MATRIX_H

#include "Matrix.h"
#include <iostream>
#include <iostream>

class NoopMatrix : public Matrix {
 public:
	NoopMatrix(size_t width, size_t height) : Matrix(width, height) {
	}

	virtual void setPixel(size_t x, size_t y, unsigned char r, unsigned char g, unsigned char b) {
    }

	virtual void update() {	
	}
};

#endif
