#include <map>
#include <vector>

#include "GrayScott.h"
#include "Drawer.h"
#include "Util.h"
#include <algorithm>

#define MAX_ROLLING_MULTIPLIER (2.0 / (30 + 1))
#define NUM_INIT_ISLANDS 5
#define ISLAND_SIZE 20

GrayScottDrawer::GrayScottDrawer(int width, int height, int palSize, Camera* camera)
: Drawer("GrayScott", width, height, palSize), m_colorIndex(0), m_camera(camera) {
    m_settings.insert(std::make_pair("speed",10));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("zoom",70));
    m_settings.insert(std::make_pair("params",0));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(1,15)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,20)));
    m_settingsRanges.insert(std::make_pair("zoom", std::make_pair(30,100)));
    m_settingsRanges.insert(std::make_pair("params", std::make_pair(0,6)));

    m_F = 0.026;
    m_k = 0.051;
    m_du = 0.08;
    m_dv = 0.04;
    m_dx = 1;
    m_dt = 1;
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
                m_u[index] = 0.5;
                m_v[index] = 0.25;
            }
        }
    }

    // params from http://mrob.com/pub/comp/xmorphia
    switch(m_settings["params"]) {
        case 0:
            m_F = 0.022;
            m_k = 0.049;
            break;
        case 1:
            m_F = 0.026;
            m_k = 0.051;
            break;
        case 2:
            m_F = 0.026;
            m_k = 0.052;
            break;
        case 3:
            m_F = 0.022;
            m_k = 0.048;
            break;
        case 4:
            m_F = 0.018;
            m_k = 0.045;
            break;
        case 5:
            m_F = 0.014;
            m_k = 0.041;
            break;
        case 6:
            m_F = 0.010;
            m_k = 0.033;
            break;
    // these parameters often cause patterns that end quickly
    //     case 7:
    //         m_F = 0.006;
    //         m_k = 0.045;
    //         break;
    //     case 8:
    //         m_F = 0.006;
    //         m_k = 0.043;
    //         break;
    //     case 9:
    //         m_F = 0.010;
    //         m_k = 0.047;
    //         break;
    }
    std::cout << "GrayScott with param set #" << m_settings["params"] << " F=" << m_F << " k=" << m_k << std::endl;
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
    maxv = m_lastMaxV + MAX_ROLLING_MULTIPLIER * (maxv - m_lastMaxV); // adapted from rolling EMA equation

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
    m_lastMaxV = maxv;
}

