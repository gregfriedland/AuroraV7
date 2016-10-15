#include "Controller.h"
#include "Colors.h"
// #include "WebServer.h"
#include "GenImage.h"
#include "Camera.h"
#include "FaceDetect.h"
#include "Util.h"
#include <signal.h>
#include "Matrix.h"
#include "HzellerRpiMatrix.h"

typedef enum {
    HZELLER_RPI_MATRX,
    SERIAL_MATRIX
} MatrixType;

#define WIDTH 64*3
#define HEIGHT 32*3
#define PAL_SIZE 1<<12 // #colors in the gradient of each palette
#define FPS 50
#define START_DRAWER "Bzr"
#define DRAWER_CHANGE_INTERVAL 20000
#define LAYOUT_LEFT_TO_RIGHT false
#define UPDATE_IMAGE_FPS 0
#define CAMERA_WIDTH 640
#define CAMERA_HEIGHT 480
#define CAMERA_FPS 0
#define FACEDETECT_FPS 0
#define MATRIX_TYPE HZELLER_RPI_MATRX

static Controller* controller;

static bool interrupted = false;

void sigHandler(int sig) {
    cout << "Caught SIGINT\n";
	// controller->stop();
    interrupted = true;
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

    Matrix* matrix = nullptr;
    switch(MATRIX_TYPE) {
        case HZELLER_RPI_MATRX:
            matrix = new HzellerRpiMatrix(WIDTH, HEIGHT);
            break;
        default:
            std::cout << "Matrix type not implemented\n";
            fail();
            break;
    }

	controller = new Controller(matrix, WIDTH, HEIGHT, PAL_SIZE, 
		baseColors, BASE_COLORS_SIZE, BASE_COLORS_PER_PALETTE,
        LAYOUT_LEFT_TO_RIGHT, startDrawer, drawerChangeInterval,
        camera, faceDetect);
	// controller->start(1000 / FPS);

    signal(SIGINT, sigHandler);
    signal(SIGKILL, sigHandler);

    uint32_t lastUpdateTime = 0;
    while(!interrupted) {
        auto now = steady_clock::now().time_since_epoch().count();
        if (now - lastUpdateTime > 1000 / FPS) {
            controller->loop();
            lastUpdateTime = now;
        }
    }

    std::cout << "Interrupted by signal\n";

	// save images to disk at recurring interval
// #if UPDATE_IMAGE_FPS > 0
//     size_t rawDataSize;
//     GenImage genImage(WIDTH, HEIGHT, "public/image.png", controller->rawData(rawDataSize));
//     genImage.start(1000 / updateImageFps);
// #endif

	//start_webserver();

	// allow accepting websocket requests from client app

    // int r = uv_run(uv_default_loop(), UV_RUN_DEFAULT);
    // assert(r == 0);

    delete matrix;
	delete controller;
    return 0;
}
