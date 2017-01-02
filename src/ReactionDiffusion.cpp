#include <map>
#include <vector>

#include "ReactionDiffusion.h"
#include "Drawer.h"
#include "Util.h"
#include <algorithm>

#define MAX_ROLLING_MULTIPLIER (2.0 / (35 * 5 + 1))
#define NUM_INIT_ISLANDS 5
#define ISLAND_SIZE 20

ReactionDiffusionDrawer::ReactionDiffusionDrawer(const std::string& name, int width, int height, int palSize)
: Drawer(name, width, height, palSize), m_colorIndex(0) {
    for (size_t q = 0; q < 2; ++q) {
        m_u[q] = new Array2D<float>(width, height);
        m_v[q] = new Array2D<float>(width, height);
    }

    m_q = true;
    m_lastMaxV = 0.5;

    m_uvUpdaterInternal = nullptr;
    m_uvUpdaterBorder = nullptr;
}

ReactionDiffusionDrawer::~ReactionDiffusionDrawer() {
    for (size_t q = 0; q < 2; ++q) {
        delete[] m_u[q];
        delete[] m_v[q];
    }
}

void ReactionDiffusionDrawer::resetRandom(float low, float high) {
    for (size_t q = 0; q < 2; ++q) {
        for (int y = 0; y < m_height; ++y) {
            for (int x = 0; x < m_width; ++x) {
                int index = x + y * m_width;
                m_u[q]->get(index) = randomFloat(low, high);
                m_v[q]->get(index) = randomFloat(low, high);
            }
        }
    }
}    

void ReactionDiffusionDrawer::resetToValues(float bgU, float bgV, float fgU, float fgV) {
    for (size_t q = 0; q < 2; ++q) {
        for (size_t i = 0; i < m_width * m_height; ++i) {
            m_u[q]->get(i) = bgU;
            m_v[q]->get(i) = bgV;
        }
    }

    for (size_t i = 0; i < NUM_INIT_ISLANDS; ++i) {
        size_t ix = random2() % (m_width - ISLAND_SIZE);
        size_t iy = random2() % (m_height - ISLAND_SIZE);
        for (size_t x = ix; x < ix + ISLAND_SIZE; ++x) {
            for (size_t y = iy; y < iy + ISLAND_SIZE; ++y) {
                size_t index = x + y * m_width;
                m_u[m_q]->get(index) = fgU;
                m_v[m_q]->get(index) = fgV;
            }
        }
    }
}


void ReactionDiffusionDrawer::draw(int* colIndices) {
    Drawer::draw(colIndices);

    float zoom = 1;

    for (size_t f = 0; f < m_speed; ++f) {
       	// std::cout << *m_v[m_q] << std::endl;

        for (size_t y = 1; y < m_height - 1; ++y) {
            for (size_t x = RDTYPE_N; x < m_width - RDTYPE_N; x += RDTYPE_N) {
	            (*m_uvUpdaterInternal)(m_u, m_v, m_q, x, y);
            }
        }

	    // borders are a special case
        for (size_t y = 0; y < m_height; y += m_height - 1) {
            for (size_t x = 0; x < m_width; x += RDTYPE_N) {
                (*m_uvUpdaterBorder)(m_u, m_v, m_q, x, y);
            }
        }
        for (size_t y = 0; y < m_height; y += 1) {
            for (size_t x = 0; x < m_width; x += m_width - RDTYPE_N) {
                (*m_uvUpdaterBorder)(m_u, m_v, m_q, x, y);
            }
        }

        m_q = 1 - m_q;
    }

    float maxv = 0;
    for (size_t y = 0; y < m_height; ++y) {
        for (size_t x = 0; x < m_width; x += 1) {
            size_t index = y * m_width + x;
            maxv = std::max(maxv, m_v[m_q]->get(index));
        }
    }
    maxv = m_lastMaxV + MAX_ROLLING_MULTIPLIER * (maxv - m_lastMaxV); // adapted from rolling EMA equation

    for (size_t y = 0; y < m_height; ++y) {
        for (size_t x = 0; x < m_width; ++x) {
            size_t index = x + y * m_width;
            float v = mapValue(m_v[m_q]->get(index), -0.25, 0.25, 0.0, 1.0);
            colIndices[index] = v * (m_palSize - 1);
        }
    }

    for (size_t y = 0; y < m_height; ++y) {
        for (size_t x = 0; x < m_width; ++x) {
            colIndices[x + y * m_width] += m_colorIndex;
        }
    }
    m_colorIndex += m_settings["colorSpeed"];
    m_lastMaxV = maxv;
}
