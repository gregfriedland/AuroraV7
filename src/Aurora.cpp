#include "Controller.h"
#include "Colors.h"
#include "WebServer.h"
#include "GenImage.h"
#include <signal.h>

#define WIDTH 64
#define HEIGHT 32
#define PAL_SIZE 1<<12 // colors in the gradient of each palette
#define FPS 40
#define START_DRAWER "Off"
#define DRAWER_CHANGE_INTERVAL 10000
#define LAYOUT_LEFT_TO_RIGHT false
#define UPDATE_IMAGE_FPS 0

// #define CAMERA_FPS 10
// var CAM_SIZE = [1280, 960];//[640, 480];
// var ENABLE_CAMERA = false;

static Controller* controller;

void sigHandler(int sig) {
	controller->stop();
	exit(0);
}

int main(int argc, char** argv) {
	string device = argc == 2 ? argv[1] : "";
	controller = new Controller(WIDTH, HEIGHT, PAL_SIZE, device, 
		baseColors, BASE_COLORS_SIZE, BASE_COLORS_PER_PALETTE,
		LAYOUT_LEFT_TO_RIGHT, START_DRAWER, FPS);
	controller->start();

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
