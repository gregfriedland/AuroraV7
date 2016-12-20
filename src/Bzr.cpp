#include <map>
#include <vector>

#include "Bzr.h"
#include "Drawer.h"
#include "Util.h"

#define BZR_SPEED_MULTIPLIER 100
#define DIFFUSION_NUM_CELLS 3
#define MIN_WIDTH 64
#define MIN_HEIGHT 32


BzrDrawer::BzrDrawer(int width, int height, int palSize, Camera* camera)
: Drawer("Bzr", width, height, palSize), m_colorIndex(0), m_camera(camera) {
    m_settings.insert(std::make_pair("speed",50));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("zoom",70));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(100,100)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,0)));

    m_bzrWidth = std::max(MIN_WIDTH, m_width);
    m_bzrHeight = std::max(MIN_HEIGHT, m_height);
    m_settingsRanges.insert(std::make_pair("zoom", std::make_pair(100,100)));
        //m_bzrWidth / width * 100 / 4, m_bzrWidth / width * 100)));

    m_state = 0;
    m_q = false;
    for (size_t q = 0; q < 2; ++q) {
        m_a[q] = new Array2D<float>(m_bzrWidth, m_bzrHeight);
        m_b[q] = new Array2D<float>(m_bzrWidth, m_bzrHeight);
        m_c[q] = new Array2D<float>(m_bzrWidth, m_bzrHeight);
    }

    m_convArr = new Array2D<float>(2 * DIFFUSION_NUM_CELLS + 1, 2 * DIFFUSION_NUM_CELLS + 1);
    for (int x = 0; x < m_convArr->width(); ++x) {
        for (int y = 0; y < m_convArr->height(); ++y) {
            size_t xDist = std::abs<int>(x - m_convArr->width() / 2);
            size_t yDist = std::abs<int>(y - m_convArr->height() / 2);
            m_convArr->get(x, y) = 1 / (1 + std::sqrt(xDist * xDist + yDist * yDist));
        }
    }
    // std::cout << "convArr:\n" << *m_convArr << std::endl;

    reset();
}

BzrDrawer::~BzrDrawer() {
    delete m_convArr;
    for (size_t q = 0; q < 2; ++q) {
        delete m_a[q];
        delete m_b[q];
        delete m_c[q];
    }
}

void BzrDrawer::reset() {
    // for (size_t x = 0; x < m_bzrWidth; ++x) {
    //     for (size_t y = 0; y < m_bzrHeight; ++y) {
    //         m_a[m_q]->get(x,y) = 0;
    //         m_b[m_q]->get(x,y) = 0;
    //         m_c[m_q]->get(x,y) = 0;
    //     }
    // }

    // for (size_t x = 0; x < 2; ++x) {
    //     for (size_t y = 0; y < 2; ++y) {
    //         m_a[m_q]->get(x,y) = 0.5;
    //         m_b[m_q]->get(x,y) = 0.5;
    //         m_c[m_q]->get(x,y) = 0.5;
    //     }
    // }

    m_a[m_q]->random();
    m_b[m_q]->random();
    m_c[m_q]->random();
}

void BzrDrawer::draw(int* colIndices) {
    float speed = m_settings["speed"] / 100.0;
    float zoom = m_settings["zoom"] / 100.0;
    int numStates = 1;//BZR_SPEED_MULTIPLIER - floor(pow(speed, 0.25) * (BZR_SPEED_MULTIPLIER-1));

    if (m_state >= numStates) {
        m_state = 0;
    }

    if (m_state == 0) {
        // std::cout << *m_a[m_q] << std::endl;

        convolve(m_convArr, m_a[m_q], m_a[1 - m_q]);
        convolve(m_convArr, m_b[m_q], m_b[1 - m_q]);
        convolve(m_convArr, m_c[m_q], m_c[1 - m_q]);

        for (size_t x = 0; x < m_bzrWidth; ++x) {
            for (size_t y = 0; y < m_bzrHeight; ++y) {
                size_t ind = x + y * m_bzrWidth;
                float c_a = (*m_a[1 - m_q])[ind];
                float c_b = (*m_b[1 - m_q])[ind];
                float c_c = (*m_c[1 - m_q])[ind];
                (*m_a[!m_q])[ind] = std::min(std::max(c_a + c_a * ( c_b - c_c ), 0.0f), 1.0f);
                (*m_b[!m_q])[ind] = std::min(std::max(c_b + c_b * ( c_c - c_a ), 0.0f), 1.0f);
                (*m_c[!m_q])[ind] = std::min(std::max(c_c + c_c * ( c_a - c_b ), 0.0f), 1.0f);
            }
        }

        m_q = 1 - m_q;
    }
  
    for (size_t x = 0; x < m_width; ++x) {
        for (size_t y = 0; y < m_height; ++y) {
            int x2 = x * zoom;
            int y2 = y * zoom;
            const float& a_q = m_a[m_q]->get(x2, y2);
            const float& a_nq = m_a[1 - m_q]->get(x2, y2);
      
            // interpolate
            float a_val = m_state * (a_q - a_nq) / numStates + a_nq;
            colIndices[x + y * m_width] = a_val * (m_palSize - 1);
        }
    }
    m_state++;  

    // for (int x = 0; x < m_width; x++) {
    //     for (int y = 0; y < m_height; y++) {
    //         colIndices[x + y * m_width] += m_colorIndex;
    //     }
    // }
    // m_colorIndex += m_settings["colorSpeed"];
}
