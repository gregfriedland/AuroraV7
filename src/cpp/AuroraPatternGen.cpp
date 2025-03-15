// Aurora for generating patterns and sending results to a Matrix

#include <signal.h>
#include <unistd.h>
#include <thread>
#include <fstream>

#include "Controller.h"
#include "Colors.h"
#include "Camera.h"
#include "FaceDetect.h"
#include "Util.h"
#include "Matrix.h"
#include "FindBeats.h"
#ifdef __arm__
    #include "HzellerRpiMatrix.h"
    #include "SerialMatrix.h"
    #include "raspicam_cv.h"
#endif
#include "ComputerScreenMatrix.h"
#include "RemoteMatrix.h"
#include "NoopMatrix.h"
#include "json.hpp"


Controller* controller = nullptr;
bool interrupted = false;

void sigHandler(int sig) {
    std::cout << "Caught SIGINT\n";
	controller->stop();
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
    ControllerSettings settings(argv[1]);
    std::ifstream ifs(argv[1]);
    nlohmann::json j;
    ifs >> j;

    // start camera before matrix
    Camera *camera = nullptr;
    if (settings.m_cameraSettings.m_fps > 0) {
        camera = new Camera(settings.m_cameraSettings);
        camera->start(1000 / settings.m_cameraSettings.m_fps);
    }

    // Create matrix
    Matrix* matrix = nullptr;
    std::string matrixType = j["matrix"];
    if (matrixType == "ComputerScreen") {
        matrix = new ComputerScreenMatrix(j["width"], j["height"]);
    } else if (matrixType == "Noop") {
        matrix = new NoopMatrix(j["width"], j["height"]);
    } else if (matrixType == "Remote") {
        matrix = new RemoteMatrix(j["width"], j["height"], j["remote"]["host"], j["remote"]["port"]);
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

    // start face detection
    FaceDetect *faceDetect = nullptr;
    if (settings.m_faceDetectFps > 0 && camera != nullptr) {
        faceDetect = new FaceDetect(camera);
        faceDetect->start(1000 / settings.m_faceDetectFps);
    }

    FindBeats *findBeats = nullptr;
    if (settings.m_findBeatsCmd.size() > 0) {
        findBeats = new FindBeats(settings.m_findBeatsCmd);
        findBeats->start();
    }

    settings.m_baseColorsPerPalette = BASE_COLORS_PER_PALETTE;
    controller = new Controller(matrix, settings, baseColors, camera, faceDetect, findBeats);

    // do it in the main thread so we can optionally display the opencv window
    while (true) {
        controller->loop(1000 / settings.m_fps);
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    
    delete matrix;
    delete camera;
    delete faceDetect;
	delete controller;
    return 0;
}
