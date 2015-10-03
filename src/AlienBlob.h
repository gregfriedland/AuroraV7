#ifndef ALIENBLOB_H
#define ALIENBLOB_H

#include "Drawer.h"
#include "Camera.h"

class AlienBlobDrawer : public Drawer {
public:
    AlienBlobDrawer(int width, int height, int palSize, Camera* camera);

    virtual void reset();

    virtual void draw(int* colIndices);

    virtual ~AlienBlobDrawer();

 private:
    float m_sineTable[360];
    int m_colorIndex;
    float m_pos;
    Camera* m_camera;
};

#endif
