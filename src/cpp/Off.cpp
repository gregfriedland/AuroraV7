#include "Off.h"

OffDrawer::OffDrawer(int width, int height, int palSize) 
: Drawer("Off", width, height, palSize), m_pos(0), m_colorIndex(0)
{}

void OffDrawer::reset() {
}

void OffDrawer::draw(int* colIndices)
{
    for (int x = 0; x < m_width; x++)
        for (int y = 0; y < m_height; y++) {
            colIndices[x + y * m_width] = ((m_pos + x) % m_width) * (m_palSize-1) / (m_width-1);
            // if (x == m_width - 1 && y == m_height - 1)
            //     cout << "max colInd=" << colIndices[x + y * m_width] << " palSize=" << m_palSize << endl;
        }
    m_pos++;
}

OffDrawer::~OffDrawer() {}
