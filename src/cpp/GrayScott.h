#ifndef GrayScott_H
#define GrayScott_H

#include "ReactionDiffusion.h"
#include "FindBeats.h"


class GrayScottDrawer : public ReactionDiffusionDrawer {
public:
    GrayScottDrawer(int width, int height, int palSize, FindBeats* findBeats);

    virtual void reset();

 protected:
    virtual void setParams();

    float m_F, m_k;
};

#endif
