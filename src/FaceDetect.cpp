#include "FaceDetect.h"
#include "Util.h"
#include <thread>


void FaceDetect::loop(unsigned int interval) {
    m_frameTimer.tick(interval, [=]() {
        m_fpsCounter.tick();

        // auto pixelData = m_camera->clonePixelData();
        // for (int x = 0; x < m_camera->width(); x++) {
        //     for (int y = 0; y < m_camera->height(); y++) {
        //         Color24 col = pixelData.get(x, y);
        //         m_image->at<unsigned char>(y,x) = (col.r + col.g + col.b) / 3;
        //     }
        // }
        auto gray = m_camera->getGrayImage();

        std::vector<cv::Rect> faces;
        // cout << "Detecting faces...\n";
        unsigned long startTime = millis();
        m_faceCascade.detectMultiScale(gray, faces, 1.1, 3,
                                       0|CV_HAAR_SCALE_IMAGE,
                                       cv::Size(100, 100));
        // cout << "done in " << millis() - startTime << "ms\n";
        if (faces.size() > 0) {
            cout << "Detected " << faces.size() << " faces\n";
            m_lastDetection = millis();
        }
    });
}

FaceDetect::FaceDetect(Camera* camera)
: m_camera(camera), m_lastDetection(0), m_fpsCounter(5000, "FaceDetect") {
    // m_image = new cv::Mat(camera->height(), camera->width(), CV_8UC1);
    if (!m_faceCascade.load(FACE_CASCADE_FILE)) {
        std::cout << "Unable to load face cascade file\n";
        exit(1);
    }
}

// FaceDetect::~FaceDetect() {
//     // delete m_image;
// }

void FaceDetect::start(unsigned int interval) {
    std::cout << "Starting face detection\n";
    m_stop = false;

    auto run = [=]() {
        while (!m_stop) {
            loop(interval);
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        m_stop = false;
    };
    m_thread = std::thread(run);
    m_thread.detach();
}

void FaceDetect::stop() {
    std::cout << "Stopping face detection\n";
    m_stop = true;
    if (m_thread.joinable()) {
        m_thread.join();
    }
}   

unsigned long FaceDetect::lastDetection() { return m_lastDetection; }
