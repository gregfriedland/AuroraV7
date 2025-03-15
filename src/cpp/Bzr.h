#ifndef BZR_H
#define BZR_H

#include "Drawer.h"
#include "Camera.h"
#include "Array2D.h"

class BzrDrawer : public Drawer {
public:
    BzrDrawer(int width, int height, int palSize, Camera* camera);

    ~BzrDrawer();

    virtual void reset();

    virtual void draw(int* colIndices);

 private:
 	size_t m_bzrWidth, m_bzrHeight;
    int m_q, m_state;
    Array2D<float> *m_a[2], *m_b[2], *m_c[2];
    float m_ka, m_kb, m_kc;
    int m_colorIndex;
    Camera* m_camera;
};

#endif
