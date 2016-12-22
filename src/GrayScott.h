#ifndef GrayScott_H
#define GrayScott_H

#include "Drawer.h"
#include "Camera.h"
#include "Util.h"
#ifdef __arm__
    #include <arm_neon.h>
    using GSTypeN = float32x4_t;
    #define VEC_N 4
#endif


using GSType = float;

class GrayScottDrawer : public Drawer {
public:
    GrayScottDrawer(int width, int height, int palSize, Camera* camera);

    ~GrayScottDrawer();

    virtual void reset();

    virtual void draw(int* colIndices);

 private:
#ifdef __arm__
    using GSArrayType = Array2DNeon<GSType,GSTypeN,VEC_N>;
    GSArrayType *m_u[2], *m_v[2];
    GSTypeN m_F, m_k, m_du, m_dv, m_dt;
#else
    Array2D<GSType> *m_u[2], *m_v[2];
    GSType m_F, m_k, m_du, m_dv, m_dt;
#endif
    bool m_q;
    int m_colorIndex;
    Camera* m_camera;
    GSType m_lastMaxV;
    GSType m_scale;
};

#endif
