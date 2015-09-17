#include "FaceDetect.h"

void FaceDetect::loop() {
    for (int x = 0; x < m_camera->width(); x++)
        for (int y = 0; y < m_camera->height(); y++) {
            Color24 col = m_camera->pixel(x, y);
            m_image->at<unsigned char>(y,x) = (col.r + col.g + col.b) / 3;
        }

    // TODO: make this async
    std::vector<cv::Rect> faces;
    cout << "Detecting faces...\n";
    m_faceCascade.detectMultiScale(*m_image, faces, 1.1, 2,
                                   0|CV_HAAR_SCALE_IMAGE, cv::Size(30, 30));
    cout << "done\n";
    m_status = faces.size() > 0;
    if (m_status)
        cout << "Detected " << faces.size() << " faces\n";
}
