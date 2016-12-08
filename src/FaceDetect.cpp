#include "FaceDetect.h"
#include "Util.h"
#include <thread>


void FaceDetect::loop() {
    auto pixelData = m_camera->clonePixelData();
    for (int x = 0; x < m_camera->width(); x++) {
        for (int y = 0; y < m_camera->height(); y++) {
            Color24 col = pixelData.get(x, y);
            m_image->at<unsigned char>(y,x) = (col.r + col.g + col.b) / 3;
        }
    }

    std::vector<cv::Rect> faces;
    cout << "Detecting faces...\n";
    unsigned long startTime = millis();
    m_faceCascade.detectMultiScale(*m_image, faces, 1.2, 2,
                                   0|CV_HAAR_SCALE_IMAGE, cv::Size(50, 50), cv::Size(400,400));
    cout << "done in " << millis() - startTime << "ms\n";
    m_status = faces.size() > 0;
    if (m_status)
        cout << "Detected " << faces.size() << " faces\n";
}

FaceDetect::FaceDetect(Camera* camera) : m_camera(camera), m_status(false) {
    m_image = new cv::Mat(camera->height(), camera->width(), CV_8UC1);
    m_faceCascade.load("src/haarcascade_frontalface_alt2.xml");
}

FaceDetect::~FaceDetect() {
    delete m_image;
}

void FaceDetect::start(unsigned int interval) {
    std::cout << "Starting face detection\n";
    m_stop = false;

    auto run = [=]() {
        while (!m_stop) {
            loop();
            std::this_thread::sleep_for(std::chrono::milliseconds(interval));
        }
        m_stop = false;
    };
    std::thread(run).detach();
}

void FaceDetect::stop() {
    std::cout << "Stopping face detection\n";
    m_stop = true;
    while (m_stop) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }    
}   

bool FaceDetect::status() { return m_status; }
