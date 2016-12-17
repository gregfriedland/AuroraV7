#include <map>
#include <vector>

#include "GrayScott.h"
#include "Drawer.h"
#include "Util.h"
#include <algorithm>

#define VMAX_INIT_PERIOD_LENGTH 30
#define VMAX_INIT_PERIOD_START 30
#define NUM_INIT_ISLANDS 3
#define ISLAND_SIZE 10

GrayScottDrawer::GrayScottDrawer(int width, int height, int palSize, Camera* camera)
: Drawer("GrayScott", width, height, palSize), m_colorIndex(0), m_camera(camera) {
    m_settings.insert(std::make_pair("speed",10));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("zoom",70));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(1,15)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,20)));
    m_settingsRanges.insert(std::make_pair("zoom", std::make_pair(30,100)));

    // params from http://mrob.com/pub/comp/xmorphia
    // 0.022/0.049 ***
    // 0.026/0.051
    // 0.026/0.052
    // 0.022/0.048
    // 0.018/0.045
    // 0.014/0.041 **
    // 0.010/0.033 ***
    // 0.006/0.045 *
    // 0.006/0.043 *
    // 0.010/0.047 **

    m_F = 0.026;
    m_k = 0.051;
    m_du = 0.08;
    m_dv = 0.04;
    m_dx = 1;
    m_dt = 1;
    // m_frameInterval = 8;
    m_rxn = 1;

    m_u = new float[m_width * m_height * 2];
    m_v = new float[m_width * m_height * 2];
    m_q = true;

    reset();
}

GrayScottDrawer::~GrayScottDrawer() {
    delete[] m_u;
    delete[] m_v;
}

void GrayScottDrawer::reset() {
    m_vMax = 0;

    for (int i = 0; i < m_width * m_height * 2; ++i) {
        m_u[i] = 1.0;
        m_v[i] = 0.0;
    }

    int qOffset = m_q * m_width * m_height;
    for (int i = 0; i < NUM_INIT_ISLANDS; ++i) {
        int ix = random2() % (m_width - ISLAND_SIZE);
        int iy = random2() % (m_height - ISLAND_SIZE);
        for (int x = ix; x < ix + ISLAND_SIZE; ++x) {
            for (int y = iy; y < iy + ISLAND_SIZE; ++y) {
                int index = x + y * m_width + qOffset;
                m_u[index] = 0.5;//(random2() % 10000) / 10000.0;
                m_v[index] = 0.25;//(random2() % 10000) / 10000.0;
            }
        }
    }
}

void GrayScottDrawer::draw(int* colIndices) {
    Drawer::draw(colIndices);

    float zoom = 1;//m_settings["zoom"] / 100.0;
    size_t speed = m_settings["speed"];

    int n = m_width * m_height * 2;
    for (int f = 0; f < speed; ++f) {
        int qOffset = m_q * m_width * m_height;
        int qOffsetNext = (!m_q) * m_width * m_height;

        for (int x = 0; x < m_width; ++x) {
            for (int y = 0; y < m_height; ++y) {
                int index = x + y * m_width + qOffset;
                int nextIndex = x + y * m_width + qOffsetNext;
                int left = (index - 1 + n) % n;
                int right = (index + 1) % n;
                int top = (index - m_width + n) % n;
                int bottom = (index + m_width) % n;

                float u = m_u[index];
                float v = m_v[index];
                float d2 = u * v * v;
                float dx2 = m_dx * m_dx;

                float d2u = m_u[left] + m_u[right] + m_u[top] + m_u[bottom] - 4 * u;
                float d2v = m_v[left] + m_v[right] + m_v[top] + m_v[bottom] - 4 * v;
                
                // diffusion
                m_u[nextIndex] = u + m_dt * m_du / dx2 * d2u;
                m_v[nextIndex] = v + m_dt * m_dv / dx2 * d2v;

                // reaction
                m_u[nextIndex] += m_dt * m_rxn * (-d2 + m_F * (1 - u));
                m_v[nextIndex] += m_dt * m_rxn * (d2 - (m_F + m_k) * v);
            }
        }
        m_q = !m_q;
    }

    int qOffset = m_q * m_width * m_height;
    float minv = 100, maxv = 0;
    for (int i = qOffset; i < qOffset + m_width * m_height; ++i) {
        float v = m_v[i];
        minv = std::min(minv, v);
        maxv = std::max(maxv, v);
    }
    if (m_frame > VMAX_INIT_PERIOD_START && m_frame <= VMAX_INIT_PERIOD_START + VMAX_INIT_PERIOD_LENGTH) {
        m_vMax = std::max(m_vMax, maxv);
        // std::cout << "vmax=" << m_vMax << std::endl;
    } else if (m_frame > VMAX_INIT_PERIOD_START + VMAX_INIT_PERIOD_LENGTH) {
        maxv = m_vMax;
    }

    for (int x = 0; x < m_width; ++x) {
        for (int y = 0; y < m_height; ++y) {
            int x2 = x * zoom;
            int y2 = y * zoom;
            float v = m_v[x2 + y2 * m_width + qOffset];

            v = mapValue(v, minv, maxv, minv, 1.0);
            colIndices[x + y * m_width] = v * (m_palSize - 1);
        }
    }

    for (int x = 0; x < m_width; ++x) {
        for (int y = 0; y < m_height; ++y) {
            colIndices[x + y * m_width] += m_colorIndex;
        }
    }
    m_colorIndex += m_settings["colorSpeed"];
}

