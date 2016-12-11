#ifndef VIDEO_H
#define VIDEO_H

#include "Drawer.h"
#include "Camera.h"
#include "Util.h"
#include <opencv2/opencv.hpp>

class VideoDrawer : public Drawer {
public:
    VideoDrawer(int width, int height, int palSize, Camera* camera);

    virtual void reset();

    virtual void draw(int* colIndices);

    virtual ~VideoDrawer();

 private:
	cv::Mat processImage(cv::Mat grayImg) const;

 	Camera* m_camera;
    int m_colorIndex;
    FrameTimer m_camFrameTimer;
    cv::Mat m_screenImg;
    ImageProcSettings m_imageProcSettings;
};

#endif
