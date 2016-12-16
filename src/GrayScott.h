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
 	// float& u(int x, int y, bool q);
 	// float& v(int x, int y, bool q);

    float *m_u, *m_v;
    bool m_q;
    float m_F, m_k, m_du, m_dv, m_dx, m_dt, m_rxn;
    int m_colorIndex, m_frameInterval;
    Camera* m_camera;
};

#endif
