#ifndef VIDEO_H
#define VIDEO_H

#include "Drawer.h"
#include "Camera.h"

class VideoDrawer : public Drawer {
public:
    VideoDrawer(int width, int height, int palSize, Camera* camera);

    virtual void reset();

    virtual void draw(int* colIndices);

    virtual ~VideoDrawer();

 private:
 	Camera* m_camera;
    int m_colorIndex;
};

#endif
