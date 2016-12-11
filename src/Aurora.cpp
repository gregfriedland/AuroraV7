#include "Controller.h"
#include "Colors.h"
#include "Camera.h"
#include "FaceDetect.h"
#include "Util.h"
#include <signal.h>
#include <unistd.h>
#include <thread>

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
