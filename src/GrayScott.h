#ifndef GrayScott_H
#define GrayScott_H

#include "Drawer.h"
#include "Util.h"
#include "Array2D.h"

using GSType = float;

#ifdef __arm__
    #include <arm_neon.h>
    using GSTypeN = float32x4_t;
    #define VEC_N 4
    using GSArrayType = Array2DNeon<GSType,GSTypeN,VEC_N>;
#endif


class GrayScottDrawer : public Drawer {
public:
    GrayScottDrawer(int width, int height, int palSize);

    ~GrayScottDrawer();

    virtual void reset();

    virtual void draw(int* colIndices);

 private:
    Array2D<GSType> *m_u[2], *m_v[2];
    GSType m_F, m_k, m_du, m_dv, m_dt;
    bool m_q;
    size_t m_colorIndex;
    size_t m_speed;
    GSType m_lastMaxV;
    GSType m_scale;
};

#endif
