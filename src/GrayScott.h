#ifndef GrayScott_H
#define GrayScott_H

#include "Drawer.h"
#include "Camera.h"

class GrayScottDrawer : public Drawer {
public:
    GrayScottDrawer(int width, int height, int palSize, Camera* camera);

    ~GrayScottDrawer();

    virtual void reset();

    virtual void draw(int* colIndices);

 private:
    int *m_u, *m_v;
    bool m_q;
    int m_F, m_k, m_du, m_dv, m_dt;
    int m_colorIndex;
    Camera* m_camera;
    int m_lastMaxV;
    int m_scale;
};

#endif
