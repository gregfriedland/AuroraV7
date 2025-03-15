#ifndef BEATBOUNCER_H
#define BEATBOUNCER_H

#include "Drawer.h"
#include "FindBeats.h"

class BeatBouncerDrawer : public Drawer {
public:
    BeatBouncerDrawer(int width, int height, int palSize, FindBeats* findBeats)
    : Drawer("BeatBouncer", width, height, palSize), m_findBeats(findBeats)
    {}

    virtual void reset() {}

    virtual void draw(int* colIndices) {
    	if (m_findBeats == nullptr)
    		return;

	    for (size_t x = 0; x < m_width; x++) {
    	    for (size_t y = 0; y < m_height; y++)
            	colIndices[x + y * m_width] = 0;
        }

    	auto onsets = m_findBeats->getOnsets();

    	for (size_t i = 0; i < onsets.size(); ++i) {
		    for (size_t x = i * m_width / onsets.size(); x < (i + 1) * m_width / onsets.size(); x++) {
	    	    for (size_t y = m_height / 2 - 10; y < m_height / 2 + 10; y++)
	            	colIndices[x + y * m_width] = (int)onsets[i] * m_palSize / 2;
	        }
	    }
    }

protected:
	FindBeats* m_findBeats;
};

#endif
