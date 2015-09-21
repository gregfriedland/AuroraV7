#ifndef OFF_H
#define OFF_H

#include "Drawer.h"
#include <iostream>

class OffDrawer : public Drawer {
public:
    OffDrawer(int width, int height, int palSize);

    virtual void reset();

    virtual void draw(int* colIndices);

    virtual ~OffDrawer();

 private:
    int m_pos;
    int m_colorIndex;
};

#endif