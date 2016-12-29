#include <map>
#include <vector>

#include "Bzr.h"
#include "Drawer.h"
#include "Util.h"

#define BZR_SPEED_MULTIPLIER 100


BzrDrawer::BzrDrawer(int width, int height, int palSize, Camera* camera)
: Drawer("Bzr", width, height, palSize), m_colorIndex(0), m_camera(camera) {
    m_settings.insert(std::make_pair("speed",50));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("zoom",70));
    m_settings.insert(std::make_pair("params",0));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(10,100)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,50)));
    m_settingsRanges.insert(std::make_pair("zoom", std::make_pair(30,150)));
    m_settingsRanges.insert(std::make_pair("params", std::make_pair(0,0)));

    m_q = 0;
    m_state = 0;

    for (size_t q = 0; q < 2; ++q) {
        m_a[q] = new Array2D<float>(width, height);
        m_b[q] = new Array2D<float>(width, height);
        m_c[q] = new Array2D<float>(width, height);
    }

    reset();
}

BzrDrawer::~BzrDrawer() {
    for (size_t q = 0; q < 2; ++q) {
        delete[] m_a[q];
        delete[] m_b[q];
        delete[] m_c[q];
    }
}

void BzrDrawer::reset() {
    for (int x = 0; x < m_width; x++) {
        for (int y = 0; y < m_height; y++) {
            int index = x + y * m_width;
            m_a[m_q]->get(index) = randomFloat(0, 1);
            m_b[m_q]->get(index) = randomFloat(0, 1);
            m_c[m_q]->get(index) = randomFloat(0, 1);
        }
    }

    switch (m_settings["params"]) {
        case 0:
            m_ka = 1.3;
            m_kb = 1.1;
            m_kc = 0.9;
            break;
        case 1:
            m_ka = 0.9;
            m_kb = 1.0;
            m_kc = 1.1;
            break;
        case 2:
            m_ka = 0.9;
            m_kb = 0.9;
            m_kc = 1.1;
            break;
        case 3:
            m_ka = 1;
            m_kb = 1;
            m_kc = 1.1;
            break;
    }

    std::cout << "Bzr with param set #" << m_settings["params"] <<
      std::setprecision(4) << " ka=" << m_ka << " kb=" << m_kb << " kc=" << m_kc << std::endl;
}

void BzrDrawer::draw(int* colIndices) {
    float speed = 1; //m_settings["speed"] / 100.0;
    float zoom = 1; //m_settings["zoom"] / 100.0;

    int numStates = BZR_SPEED_MULTIPLIER - std::floor(std::pow(speed, 0.25) * (BZR_SPEED_MULTIPLIER-1));

    if (m_state >= numStates)
        m_state = 0;

    if (m_state == 0) {
        for (int y = 0; y < m_height; ++y) {
            for (int x = 0; x < m_width; ++x) {
                float c_a=0, c_b=0, c_c=0;

                for (int j=y-1; j<=y+1; j++) {
                    int jj = (j + m_height) % m_height;
                    for (int i=x-1; i<=x+1; i++) {
                        size_t ii = (i + m_width) % m_width;
                        size_t ind = ii + jj * m_width;
                        c_a += m_a[m_q]->get(ind);
                        c_b += m_b[m_q]->get(ind);
                        c_c += m_c[m_q]->get(ind);
                    }
                }

                c_a /= 9;
                c_b /= 9;
                c_c /= 9;

                size_t ind = x + y * m_width;
                m_a[1 - m_q]->get(ind) = std::min(std::max(c_a + c_a * ( m_ka * c_b - m_kc * c_c ), 0.0f), 1.0f);
                m_b[1 - m_q]->get(ind) = std::min(std::max(c_b + c_b * ( m_kb * c_c - m_ka * c_a ), 0.0f), 1.0f);
                m_c[1 - m_q]->get(ind) = std::min(std::max(c_c + c_c * ( m_kc * c_a - m_kb * c_b ), 0.0f), 1.0f);
            }
        }
        m_q = 1 - m_q;
    }
      
    for (size_t y = 0; y < m_height; ++y) {
        for (size_t x = 0; x < m_width; x++) {
            size_t x2 = x * zoom;
            size_t y2 = y * zoom;
            size_t ind = x2 + y2 * m_width;
            float aNext = m_a[m_q]->get(ind);
            float aPrev = m_a[1 - m_q]->get(ind);

            // interpolate
            float val = m_state * (aNext - aPrev) / numStates + aPrev;
            colIndices[x + y * m_width] = val * (m_palSize - 1);
        }
      }
      m_state++;  

    for (size_t x = 0; x < m_width; x++) {
        for (size_t y = 0; y < m_height; y++) {
            colIndices[x + y * m_width] += m_colorIndex;
        }
    }

    m_colorIndex += m_settings["colorSpeed"];
}
