// Aurora for controlling pixels only (no frills like camera or audio)
#include <signal.h>
#include <unistd.h>
#include <thread>
#include <fstream>
#include <array>

#include "Matrix.h"
#include "Util.h"
#ifdef __arm__
    #include "HzellerRpiMatrix.h"
    #include "SerialMatrix.h"
    #include "raspicam_cv.h"
#endif
#include "ComputerScreenMatrix.h"
#include "NoopMatrix.h"
#include "json.hpp"
#include "md5.h"

#define ASIO_STANDALONE
#include <asio.hpp>

using asio::ip::tcp;


bool interrupted = false;

void sigHandler(int sig) {
    std::cout << "Caught SIGINT\n";
	fail();
}

void loop(size_t width, size_t height, Matrix* matrix, asio::io_service& io_service, size_t port) {    
    matrix->update();

    static std::string packet;
    packet.resize(65535);
    std::string buffer;

    tcp::acceptor acceptor(io_service, tcp::endpoint(tcp::v4(), port));
    while (buffer.size() < width * height * 3) {
        tcp::socket socket(io_service);
        acceptor.accept(socket);
        std::cout << "Accepted socket" << std::endl;

        asio::error_code error;
        size_t packetSize = socket.read_some(
            asio::buffer(&packet[0], packet.size()), error);
        if (error == asio::error::eof) {
            std::cerr << "connection closed" << std::endl;
            return; // Connection closed cleanly by peer.
        } else if (packetSize < 16) {
            std::cerr << "Unexpected packet size: " << packetSize << std::endl;
            continue;
        } else if (error)
            throw asio::system_error(error); // Some other error.

        // verify packet
        std::string md5Expected = packet.substr(0, 16);
        std::string payload = packet.substr(16, packetSize - 16);
        std::cout << "Received payload (" << payload.size() << ")" << std::endl;
        std::string md5Calculated = hexToBytes(md5(payload));
        if (md5Expected != md5Calculated) {
            std::cerr << "Unexpected md5: " << bytesToHex(md5Expected) << " != " << bytesToHex(md5Calculated) << std::endl;
            asio::write(socket, asio::buffer("failure", 4));
            continue;
        }
        buffer += payload;

        asio::write(socket, asio::buffer("success", 7));
    }

    if (buffer.size() != width * height * 3) {
        std::cerr << "Invalid frame size: " << std::to_string(buffer.size()) << std::endl;
        return;
    } else {
        std::cout << "Received frame!" << std::endl;
    }

    // update output matrix
    for (size_t y = 0; y < (size_t) height; y++) {
        for (size_t x = 0; x < (size_t) width; x++) {
            size_t index = (width * y + x) * 3;
            matrix->setPixel(x, y, buffer[index], buffer[index + 1], buffer[index + 2]);
        }
    }
}

int main(int argc, char** argv) {
    struct sigaction sigIntHandler;
    sigIntHandler.sa_handler = sigHandler;
    sigemptyset(&sigIntHandler.sa_mask);
    sigIntHandler.sa_flags = 0;
    sigaction(SIGINT, &sigIntHandler, NULL);
    signal(SIGINT, sigHandler);
    signal(SIGKILL, sigHandler);

    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <json-config>" << std::endl;
        exit(1);
    }
    std::ifstream ifs(argv[1]);
    nlohmann::json j;
    ifs >> j;

    // Create matrix
    Matrix* matrix = nullptr;
    std::string matrixType = j["matrix"];
    if (matrixType == "ComputerScreen") {
        matrix = new ComputerScreenMatrix(j["width"], j["height"]);
    } else if (matrixType == "Noop") {
        matrix = new NoopMatrix(j["width"], j["height"]);
#ifdef __arm__
    } else if (matrixType == "HzellerRpi") {
        matrix = new HzellerRpiMatrix(j["width"], j["height"]);
    } else if (matrixType == "Serial") {
        matrix = new SerialMatrix(j["width"], j["height"], j["serialDevice"]);
#endif
    } else {
        std::cerr << "Matrix type '" << j["matrix"] << "' not implemented\n";
        exit(1);
    }

    size_t port = j["networkPort"];
    try {
        asio::io_service io_service;

        // size_t interval = 1000 / (size_t)j["fps"];
        FrameTimer frameTimer;
        while (true) {
            // frameTimer.tick(interval, [&]() {
                loop(j["width"], j["height"], matrix, io_service, port);
            // });
        }

        delete matrix;
        return 0;
    } catch (std::exception& e) {
        std::cerr << "Exception: " << e.what() << std::endl;
        return 1;
    }
}
