// Aurora for controlling pixels only (no frills like camera or audio)
#include <signal.h>
#include <unistd.h>
#include <thread>
#include <fstream>
#include <array>

#include <grpc/grpc.h>

#include "Matrix.h"
#include "Util.h"
#ifdef __arm__
    #include "HzellerRpiMatrix.h"
    #include "SerialMatrix.h"
#endif
#include "ComputerScreenMatrix.h"
#include "NoopMatrix.h"
#include "json.hpp"
#include "AuroraServer.h"


bool interrupted = false;

void sigHandler(int sig) {
    std::cout << "Caught SIGINT\n";
	fail();
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

    try {
        std::string addr("0.0.0.0:" + std::to_string((size_t) j["networkPort"]));
        AuroraServer service(matrix);

        ServerBuilder builder;
        builder.AddListeningPort(addr, grpc::InsecureServerCredentials());
        builder.RegisterService(&service);
        std::unique_ptr<Server> server(builder.BuildAndStart());
        std::cout << "Server listening on " << addr << std::endl;
        server->Wait();

        delete matrix;
        return 0;
    } catch (std::exception& e) {
        std::cerr << "Exception: " << e.what() << std::endl;
        return 1;
    }
}
