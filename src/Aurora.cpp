#include "Controller.h"
#include "Colors.h"
#include "Camera.h"
#include "FaceDetect.h"
#include "Util.h"
#include <signal.h>
#include <unistd.h>
#include <thread>

#define WIDTH 64
#define HEIGHT 32
#define PAL_SIZE 1<<12 // #colors in the gradient of each palette
#define FPS 35
#define START_DRAWER "Video"
#define DRAWER_CHANGE_INTERVAL 30000
#define LAYOUT_LEFT_TO_RIGHT false
#define CAMERA_WIDTH 1280
#define CAMERA_HEIGHT 720
#define CAMERA_FPS 15
#define FACEDETECT_FPS 1
#define FACE_VIDEO_DRAWER_TIMEOUT 10000

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

    ControllerSettings settings;

	settings.m_device = argc >= 2 ? argv[1] : "";
    
    settings.m_startDrawerName = argc >= 3 ? argv[2] : START_DRAWER;
    settings.m_drawerChangeInterval = argc >= 4 ? atoi(argv[3]) : DRAWER_CHANGE_INTERVAL;
    int cameraFps = argc >= 5 ? atoi(argv[4]) : CAMERA_FPS;
    float facedetectFps = argc >= 6 ? atof(argv[5]) : FACEDETECT_FPS;
    settings.m_showInWindowMultiplier = argc >= 7 ? atof(argv[6]) : false;

    std::cout << "fps = " << FPS << std::endl;
    std::cout << "drawerChangeInterval = " << settings.m_drawerChangeInterval << std::endl;
    std::cout << "cameraFps = " << cameraFps << std::endl;
    std::cout << "facedetectFps = " << facedetectFps << std::endl;
    std::cout << "showInWindowMultiplier = " << settings.m_showInWindowMultiplier << std::endl;
    std::cout << std::endl;

    signal(SIGINT, sigHandler);
    signal(SIGKILL, sigHandler);

	// start camera
    Camera *camera = NULL;
    if (cameraFps > 0) {
        camera = new Camera(CAMERA_WIDTH, CAMERA_HEIGHT);
        camera->start(1000 / cameraFps);
    }

	// start face detection
    FaceDetect *faceDetect = NULL;
    if (facedetectFps > 0 && camera != NULL) {
        faceDetect = new FaceDetect(camera);
        faceDetect->start(1000 / facedetectFps);
    }

    settings.m_width = WIDTH;
    settings.m_height = HEIGHT;
    settings.m_palSize = PAL_SIZE;
    settings.m_numBaseColors = BASE_COLORS_SIZE;
    settings.m_baseColorsPerPalette = BASE_COLORS_PER_PALETTE;
    settings.m_layoutLeftToRight = LAYOUT_LEFT_TO_RIGHT;
    settings.m_faceVideoDrawerTimeout = FACE_VIDEO_DRAWER_TIMEOUT;
	controller = new Controller(settings, baseColors, camera, faceDetect);

    // do it in the main thread so we can optionally display the opencv window
    while (true) {
        controller->loop(1000 / FPS);
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    delete camera;
    delete faceDetect;
	delete controller;
    return 0;
}
