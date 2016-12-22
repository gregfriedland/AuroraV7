#ifndef GrayScott_H
#define GrayScott_H

#include "Drawer.h"
#include "Camera.h"
#include "Util.h"

#ifdef __arm__
    using GSType = __fp16;
#else
    using GSType = float;
#endif

class GrayScottDrawer : public Drawer {
public:
    GrayScottDrawer(int width, int height, int palSize, Camera* camera);

    ~GrayScottDrawer();

    virtual void reset();

    virtual void draw(int* colIndices);

 private:

    Array2D<GSType> *m_u[2], *m_v[2];
    bool m_q;
    GSType m_F, m_k, m_du, m_dv, m_dt;
    int m_colorIndex;
    Camera* m_camera;
    GSType m_lastMaxV;
    GSType m_scale;
};

#endif
