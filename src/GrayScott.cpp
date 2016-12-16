#include <map>
#include <vector>

#include "GrayScott.h"
#include "Drawer.h"
#include "Util.h"

// #define GRAY_SCOTT_SPEED_MULTIPLIER 100
#define NUM_INIT_ISLANDS 5
#define ISLAND_SIZE 20

GrayScottDrawer::GrayScottDrawer(int width, int height, int palSize, Camera* camera)
: Drawer("GrayScott", width, height, palSize), m_colorIndex(0), m_camera(camera) {
    m_settings.insert(make_pair("speed",50));
    m_settings.insert(make_pair("colorSpeed",0));
    m_settings.insert(make_pair("zoom",70));
    m_settingsRanges.insert(make_pair("speed", make_pair(0,100)));
    m_settingsRanges.insert(make_pair("colorSpeed", make_pair(0,50)));
    m_settingsRanges.insert(make_pair("zoom", make_pair(30,100)));

    m_F = 0.008;
    m_k = 0.031;
    m_du = 0.0385;
    m_dv = 0.008;
    m_dx = 1;//0.009766;
    m_dt = 1; //0.1;
    m_frameInterval = 8;
    m_rxn = 0.6;

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
                m_u[index] = 0.5;//(random2() % 10000) / 10000.0;
                m_v[index] = 0.25;//(random2() % 10000) / 10000.0;
            }
        }
    }
}

void GrayScottDrawer::draw(int* colIndices) {
    float zoom = 1; //m_settings["zoom"] / 100.0;

    for (int f = 0; f < m_frameInterval; ++f) {
        int qOffset = m_q * m_width * m_height;
        int qOffsetNext = (!m_q) * m_width * m_height;

        for (int x = 1; x < m_width - 1; ++x) {
            for (int y = 1; y < m_height - 1; ++y) {
                int index = x + y * m_width + qOffset;
                int nextIndex = x + y * m_width + qOffsetNext;
                int left = index - 1;
                int right = index + 1;
                int top = index - m_width;
                int bottom = index + m_width;

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
    for (int x = 0; x < m_width; ++x) {
        for (int y = 0; y < m_height; ++y) {
            int x2 = x * zoom;
            int y2 = y * zoom;

            colIndices[x + y * m_width] = m_v[x2 + y2 * m_width + qOffset] * (m_palSize - 1);
        }
    }

    // for (int x = 0; x < m_width; ++x) {
    //     for (int y = 0; y < m_height; ++y) {
    //         colIndices[x + y * m_width] += m_colorIndex;
    //     }
    // }

    // m_colorIndex += m_settings["colorSpeed"];
}

