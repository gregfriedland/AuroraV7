#include "Controller.h"
#include "Colors.h"
#include "WebServer.h"
#include "GenImage.h"
#include "Camera.h"
#include "FaceDetect.h"
#include <signal.h>

#define WIDTH 64
#define HEIGHT 32
#define PAL_SIZE 1<<12 // #colors in the gradient of each palette
#define FPS 40
#define START_DRAWER "Video"
#define DRAWER_CHANGE_INTERVAL 60000
#define LAYOUT_LEFT_TO_RIGHT false
#define UPDATE_IMAGE_FPS 0
#define CAMERA_WIDTH 1280
#define CAMERA_HEIGHT 960
#define CAMERA_FPS 10
#define FACEDETECT_FPS 0.5

static Controller* controller;

void sigHandler(int sig) {
	controller->stop();
	exit(0);
}

int main(int argc, char** argv) {
	string device = argc == 2 ? argv[1] : "";
    
	// start camera
    Camera *camera = NULL;
    if (CAMERA_FPS > 0) {
        camera = new Camera(CAMERA_WIDTH, CAMERA_HEIGHT);
        camera->start(1000 / CAMERA_FPS);
    }

	// start face detection
    FaceDetect *faceDetect = NULL;
    if (FACEDETECT_FPS > 0 && camera != NULL) {
        faceDetect = new FaceDetect(camera);
        faceDetect->start(1000 / FACEDETECT_FPS);
    }

	controller = new Controller(WIDTH, HEIGHT, PAL_SIZE, device, 
		baseColors, BASE_COLORS_SIZE, BASE_COLORS_PER_PALETTE,
        LAYOUT_LEFT_TO_RIGHT, START_DRAWER, DRAWER_CHANGE_INTERVAL,
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

	start_webserver();

	// allow accepting websocket requests from client app

	delete controller;
}
