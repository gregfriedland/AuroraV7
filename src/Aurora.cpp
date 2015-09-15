#include "Controller.h"
#include "Colors.h"
#include "WebServer.h"
#include "GenImage.h"

#define WIDTH 64
#define HEIGHT 32
#define PAL_SIZE 1<<12 // colors in the gradient of each palette
#define FPS 40
#define START_DRAWER "AlienBlob"
#define DRAWER_CHANGE_INTERVAL 10000
#define LAYOUT_LEFT_TO_RIGHT false
#define UPDATE_IMAGE_FPS 5

// #define CAMERA_FPS 10
// var CAM_SIZE = [1280, 960];//[640, 480];
// var ENABLE_CAMERA = false;


int main(int argc, char** argv) {
	assert(argc == 2);
	Controller controller(WIDTH, HEIGHT, PAL_SIZE, argv[1], 
		baseColors, BASE_COLORS_SIZE, BASE_COLORS_PER_PALETTE,
		LAYOUT_LEFT_TO_RIGHT, START_DRAWER, FPS);
	controller.start();

	// save images to disk at recurring interval
	if (UPDATE_IMAGE_FPS > 0) {
		int rawDataSize;
		GenImage genImage(WIDTH, HEIGHT, "public/image.png", controller.rawData(rawDataSize));
		genImage.start(1000 / UPDATE_IMAGE_FPS);
	}

	start_webserver();

	// allow accepting websocket requests from client app
}
