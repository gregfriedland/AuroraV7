#include "Controller.h"
#include "Colors.h"
#include "Camera.h"
#include "FaceDetect.h"
#include "Util.h"
#include <signal.h>
#include <unistd.h>
#include <thread>

// #define WIDTH 64
// #define HEIGHT 32
// #define PAL_SIZE 1<<12 // #colors in the gradient of each palette
// #define FPS 35
// #define START_DRAWER "Video"
// #define DRAWER_CHANGE_INTERVAL 30000
// #define LAYOUT_LEFT_TO_RIGHT false
// #define CAMERA_WIDTH 1280
// #define CAMERA_HEIGHT 720
// #define CAMERA_FPS 15
// #define FACEDETECT_FPS 1
// #define FACE_VIDEO_DRAWER_TIMEOUT 10000

static Controller* controller;

void sigHandler(int sig) {
    cout << "Caught SIGINT\n";
	controller->stop();
	fail();
}

int main(int argc, char** argv) {
    struct sigaction sigIntHandler;
    sigIntHandler.sa_handler = sigHandler;
    sigemptyset(&sigIntHandler.sa_mask);
    sigIntHandler.sa_flags = 0;
    sigaction(SIGINT, &sigIntHandler, NULL);

    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <json-config>" << std::endl;
        exit(1);
    }
    ControllerSettings settings(argv[1]);

    signal(SIGINT, sigHandler);
    signal(SIGKILL, sigHandler);

	// start camera
    Camera *camera = NULL;
    if (settings.m_cameraFps > 0) {
        camera = new Camera(settings.m_cameraWidth, settings.m_cameraHeight);
        camera->start(1000 / settings.m_cameraFps);
    }

	// start face detection
    FaceDetect *faceDetect = NULL;
    if (settings.m_faceDetectFps > 0 && camera != NULL) {
        faceDetect = new FaceDetect(camera);
        faceDetect->start(1000 / settings.m_faceDetectFps);
    }

    settings.m_numBaseColors = BASE_COLORS_SIZE;
    settings.m_baseColorsPerPalette = BASE_COLORS_PER_PALETTE;
	controller = new Controller(settings, baseColors, camera, faceDetect);

    // do it in the main thread so we can optionally display the opencv window
    while (true) {
        controller->loop(1000 / settings.m_fps);
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    delete camera;
    delete faceDetect;
	delete controller;
    return 0;
}
