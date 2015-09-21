#include "FaceDetect.h"
#include "Util.h"

void FaceDetect::loop() {
    for (int x = 0; x < m_camera->width(); x++)
        for (int y = 0; y < m_camera->height(); y++) {
            Color24 col = m_camera->pixel(x, y);
            m_image->at<unsigned char>(y,x) = (col.r + col.g + col.b) / 3;
        }

    // TODO: make this async
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
    m_work.data = this;
    uv_timer_init(uv_default_loop(), &m_timer);
    m_timer.data = this;
    uv_timer_start(&m_timer, facedetect_timer_cb, 0, interval);
    std::cout << "Starting face detection\n";
}

void FaceDetect::stop() {
    std::cout << "Stopping face detection\n";
    uv_timer_stop(&m_timer);
}   

bool FaceDetect::status() { return m_status; }


inline static void facedetect_timer_cb(uv_timer_t* handle) {
    uv_work_t *work = &((FaceDetect*)handle->data)->m_work;
    uv_queue_work(uv_default_loop(), work, facedetect_async, NULL);
}

inline static void facedetect_async(uv_work_t* work) {
    ((FaceDetect*)work->data)->loop();
}
