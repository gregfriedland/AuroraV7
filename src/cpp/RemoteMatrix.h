#ifndef REMOTE_MATRIX_H
#define REMOTE_MATRIX_H

#include "Matrix.h"
#include <iostream>
#include <string>
#include "AuroraClient.h"


class RemoteMatrix : public Matrix {
 public:
	RemoteMatrix(size_t width, size_t height, const std::string& hostname, size_t port)
    : Matrix(width, height),
      m_client(AuroraClient(grpc::CreateChannel(hostname + ":" + std::to_string(port),
            grpc::InsecureChannelCredentials()))) {
        std::cout << "Connected to " << hostname << ":" << port << std::endl;

        m_data.resize(width * height * 3);
    }

	virtual void setPixel(size_t x, size_t y, unsigned char r, unsigned char g, unsigned char b) {
        size_t index = (y * m_width + x) * 3;
        m_data[index] = r;
        m_data[index + 1] = g;
        m_data[index + 2] = b;
    }

	virtual void update() {
        m_client.sendFrame(m_data);
	}

 private:
    AuroraClient m_client;
    std::string m_data;
};

#endif
