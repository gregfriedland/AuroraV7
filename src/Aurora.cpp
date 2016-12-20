#include "Controller.h"
#include "Colors.h"
#include "Camera.h"
#include "FaceDetect.h"
#include "Util.h"
#include <signal.h>
#include <unistd.h>
#include <thread>
#include "Matrix.h"
#include "HzellerRpiMatrix.h"

// #define MATRIX_TYPE HZELLER_RPI_MATRX

static Controller* controller;

static bool interrupted = false;

void sigHandler(int sig) {
    std::cout << "Caught SIGINT\n";
	controller->stop();
    cout << "Caught SIGINT\n";
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

    signal(SIGINT, sigHandler);
    signal(SIGKILL, sigHandler);

    // Create matrix
    Matrix* matrix = nullptr;
    switch(settings.m_matrixType) {
        case HZELLER_RPI_MATRX:
            matrix = new HzellerRpiMatrix(settings.m_width, settings.m_height);
            break;
        case SERIAL_MATRX:
            matrix = new SerialMatrix(settings.m_width, settings.m_height);
            break;
        case COMPUTER_SCREEN_MATRIX:
            matrix = new ComputerScreenMatrix(settings.m_width, settings.m_height);
            break;
        default:
            std::cerr << "Matrix type not implemented\n";
            exit(1);
            break;
    }

	// start camera
    Camera *camera = NULL;
    if (settings.m_cameraSettings.m_fps > 0) {
        camera = new Camera(settings.m_cameraSettings);
        camera->start(1000 / settings.m_cameraSettings.m_fps);
    }

    // start face detection
    FaceDetect *faceDetect = NULL;
    if (settings.m_faceDetectFps > 0 && camera != NULL) {
        faceDetect = new FaceDetect(camera);
        faceDetect->start(1000 / settings.m_faceDetectFps);
    }

    settings.m_baseColorsPerPalette = BASE_COLORS_PER_PALETTE;
    controller = new Controller(matrix, settings, baseColors, camera, faceDetect);

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
