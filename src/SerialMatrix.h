#ifndef SERIAL_MATRIX_H
#define SERIAL_MATRIX_H

#include "Matrix.h"
#include "Serial.h"
#include <iostream>

class SerialMatrix : public Matrix {
 public:
	SerialMatrix(size_t width, size_t height, const std::string& device)
	: Matrix(width, height), m_device(device), m_serial(device) {
		// create serial connection
		if (m_device.size() > 0) {
			m_serial.connect();
		}

	    m_serialWriteBufferSize = width * height * 3 + 1;
	    m_serialWriteBuffer = new unsigned char[m_serialWriteBufferSize];		
	}

	virtual ~SerialMatrix() {
		if (m_device.size() > 0) {
	        std::cout << "Closing serial port\n";
			m_serial.close();
		}
		delete m_serialWriteBuffer;
	}

	virtual void setPixel(size_t x, size_t y, unsigned char r, unsigned char g, unsigned char b) {
		size_t index = (y * m_width + x) * 3;
		m_serialWriteBuffer[index] = std::min((unsigned char)254, r);
		m_serialWriteBuffer[index + 1] = std::min((unsigned char)254, g);
		m_serialWriteBuffer[index + 2] = std::min((unsigned char)254, b);
	}

	virtual void update() {	
		// data is already packed for serial transmission
		m_serialWriteBuffer[m_serialWriteBufferSize - 1] = 255;

		// send serial data
		if (m_device.size() > 0) {
			m_serial.write(m_serialWriteBuffer, m_serialWriteBufferSize);

			unsigned char buffer[256];
			if (m_serial.read(256, buffer) > 0)
			  std::cout << "read: " << (unsigned int) buffer[0] << std::endl;
		}
	}

 private:
 	std::string m_device;
 	Serial m_serial;
    unsigned char* m_serialWriteBuffer; // stores data in serial write order
    size_t m_serialWriteBufferSize; 	
};

#endif
