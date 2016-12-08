#include "Controller.h"
#include "Colors.h"
#include "WebServer.h"
#include "GenImage.h"
#include "Camera.h"
#include "FaceDetect.h"
#include "Util.h"
#include <signal.h>
#include <unistd.h>

#define WIDTH 64
#define HEIGHT 32
#define PAL_SIZE 1<<12 // #colors in the gradient of each palette
#define FPS 30
#define START_DRAWER "Bzr"
#define DRAWER_CHANGE_INTERVAL 30000
#define LAYOUT_LEFT_TO_RIGHT false
#define UPDATE_IMAGE_FPS 0
#define CAMERA_WIDTH 640
#define CAMERA_HEIGHT 480
#define CAMERA_FPS 15
#define FACEDETECT_FPS 0.2

static Controller* controller;

void sigHandler(int sig) {
    cout << "Caugt SIGINT\n";
	controller->stop();
	fail();
}

int main(int argc, char** argv) {
    struct sigaction sigIntHandler;
    sigIntHandler.sa_handler = sigHandler;
    sigemptyset(&sigIntHandler.sa_mask);
    sigIntHandler.sa_flags = 0;
    sigaction(SIGINT, &sigIntHandler, NULL);

	string device = argc >= 2 ? argv[1] : "";
    
    string startDrawer = argc >= 3 ? argv[2] : START_DRAWER;
    int drawerChangeInterval = argc >= 4 ? atoi(argv[3]) : DRAWER_CHANGE_INTERVAL;
    int cameraFps = argc >= 5 ? atoi(argv[4]) : CAMERA_FPS;
    float facedetectFps = argc >= 6 ? atof(argv[5]) : FACEDETECT_FPS;

    // wait a bit for things to settle
    //sleep(30);

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

	controller = new Controller(WIDTH, HEIGHT, PAL_SIZE, device, 
		baseColors, BASE_COLORS_SIZE, BASE_COLORS_PER_PALETTE,
        LAYOUT_LEFT_TO_RIGHT, startDrawer, drawerChangeInterval,
        camera, faceDetect);
	controller->start(1000 / FPS);

    signal(SIGINT, sigHandler);
    signal(SIGKILL, sigHandler);

	// save images to disk at recurring interval
	int updateImageFps = device.size() != 0 ? UPDATE_IMAGE_FPS : 5;
	if (updateImageFps > 0 ) {
		int rawDataSize;
		GenImage genImage(WIDTH, HEIGHT, "public/image.png", controller->rawData(rawDataSize));
		genImage.start(1000 / updateImageFps);
	}

	//start_webserver();

	// allow accepting websocket requests from client app

    int r = uv_run(uv_default_loop(), UV_RUN_DEFAULT);
    assert(r == 0);

	delete controller;
    return r;
}
