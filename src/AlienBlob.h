#ifndef ALIENBLOB_H
#define ALIENBLOB_H

#include "Drawer.h"

class AlienBlobDrawer : public Drawer {
public:
    AlienBlobDrawer(int width, int height, int palSize);

    virtual void reset();

    virtual void draw(int* colIndices);

    virtual ~AlienBlobDrawer();

 private:
    float m_sineTable[360];
    int m_colorIndex;
    float m_pos;
};

#endif