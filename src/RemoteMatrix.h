#ifndef REMOTE_MATRIX_H
#define REMOTE_MATRIX_H

#include "Matrix.h"
#include "md5.h"
#include <iostream>
#include <string>

#define ASIO_STANDALONE
#include <asio.hpp>

using asio::ip::tcp;

#define MAX_PACKET_SIZE 20000

class RemoteMatrix : public Matrix {
 public:
	RemoteMatrix(size_t width, size_t height, const std::string& hostname, size_t port)
    : Matrix(width, height) {
        std::cout << "Connecting to " << hostname << std::endl;

        m_endpoint = asio::ip::tcp::endpoint(asio::ip::address::from_string(hostname), port);

        m_request.resize(width * height * 3);
	}

	virtual void setPixel(size_t x, size_t y, unsigned char r, unsigned char g, unsigned char b) {
        size_t index = (y * m_width + x) * 3;
        m_request[index] = r;
        m_request[index + 1] = r;
        m_request[index + 2] = r;
    }

	virtual void update() {
        size_t bytesWritten = 0;
        while (bytesWritten < m_request.size()) {
            tcp::socket socket(m_io_service);
            asio::error_code err;
            std::cout << "connecting to socket" << std::endl;
            socket.connect(m_endpoint, err);
            if (err) {
                std::cout << "Connect error: " << err.message() << std::endl;
                break;
            }

            std::string packet = m_request.substr(bytesWritten, std::min(m_request.size() - bytesWritten, (size_t)MAX_PACKET_SIZE));
            packet = hexToBytes(md5(packet)) + packet;           
            std::cout << "sending packet (" << packet.size() << ")" << std::endl;
            asio::write(socket, asio::buffer(packet.c_str(), packet.size()));

            std::cout << "reading reply" << std::endl;
            std::string reply;
            reply.resize(1024);
            asio::error_code error;
            size_t replySize = socket.read_some(asio::buffer(&reply[0], reply.size()), error);
            if (error == asio::error::eof) {
                std::cerr << "connection closed" << std::endl;
                return; // Connection closed cleanly by peer.
            }
            else if (error)
                throw asio::system_error(error); // Some other error.

            if (reply.substr(0, replySize) == "success") {
                std::cout << "packet succeeded" << std::endl;
                bytesWritten += packet.size() - 16;
            } else {
                std::cerr << "packet failed: '" << reply.substr(0, replySize) << "'" << std::endl;
            }
        }
        std::cout << "frame succeeded" << std::endl;        
	}

 private:
    asio::io_service m_io_service;
    asio::ip::tcp::endpoint m_endpoint;
    std::string m_request;
};

#endif
