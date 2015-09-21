#ifndef BZR_H
#define BZR_H

#include "Drawer.h"

class BzrDrawer : public Drawer {
public:
    BzrDrawer(int width, int height, int palSize);

    ~BzrDrawer();

    virtual void reset();

    virtual void draw(int* colIndices);

 private:
    int m_p, m_q, m_state;
    float *m_a, *m_b, *m_c;
    int m_colorIndex;
};

#endif