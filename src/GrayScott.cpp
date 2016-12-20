#include <map>
#include <vector>

#include "GrayScott.h"
#include "Drawer.h"
#include "Util.h"
#include <algorithm>

#define MAX_ROLLING_MULTIPLIER (2.0 / (35 * 5 + 1))
#define NUM_INIT_ISLANDS 5
#define ISLAND_SIZE 20

#define FIXED_PT_SHIFT 10
#define TO_FP(f) ((int)(f * (1<<FIXED_PT_SHIFT)))
#define FROM_FP(i) (i >> FIXED_PT_SHIFT)
#define FP_TO_FLOAT(i) ((float)(i>>FIXED_PT_SHIFT))

GrayScottDrawer::GrayScottDrawer(int width, int height, int palSize, Camera* camera)
: Drawer("GrayScott", width, height, palSize), m_colorIndex(0), m_camera(camera) {
    m_settings.insert(std::make_pair("speed",10));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("params",1));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(10,10)));//5,25)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,0)));//,10)));
    m_settingsRanges.insert(std::make_pair("params", std::make_pair(0,0)));//8)));

    m_u = new int[m_width * m_height * 2];
    m_v = new int[m_width * m_height * 2];
    m_q = true;

    m_lastMaxV = TO_FP(0.5);
    reset();
}

GrayScottDrawer::~GrayScottDrawer() {
    delete[] m_u;
    delete[] m_v;
}

void GrayScottDrawer::reset() {
    for (size_t i = 0; i < m_width * m_height * 2; ++i) {
        m_u[i] = TO_FP(1.0);
        m_v[i] = TO_FP(0.0);
    }

    size_t qOffset = m_q * m_width * m_height;
    for (size_t i = 0; i < NUM_INIT_ISLANDS; ++i) {
        size_t ix = random2() % (m_width - ISLAND_SIZE);
        size_t iy = random2() % (m_height - ISLAND_SIZE);
        for (size_t x = ix; x < ix + ISLAND_SIZE; ++x) {
            for (size_t y = iy; y < iy + ISLAND_SIZE; ++y) {
                size_t index = x + y * m_width + qOffset;
                m_u[index] = TO_FP(0.5);
                m_v[index] = TO_FP(0.25);
            }
        }
    }

    // params from http://mrob.com/pub/comp/xmorphia
    switch(m_settings["params"]) {
        case 0:
            m_F = TO_FP(0.022);
            m_k = TO_FP(0.049);
            m_scale = TO_FP(5);//std::exp(randomFloat(std::log(0.3), std::log(20)));
            break;
        case 1:
            m_F = TO_FP(0.026);
            m_k = TO_FP(0.051);
            m_scale = TO_FP(std::exp(randomFloat(std::log(0.3), std::log(20))));
            break;
        case 2:
            m_F = TO_FP(0.026);
            m_k = TO_FP(0.052);
            m_scale = TO_FP(std::exp(randomFloat(std::log(0.3), std::log(20))));
            break;
        case 3:
            m_F = TO_FP(0.022);
            m_k = TO_FP(0.048);
            m_scale = TO_FP(std::exp(randomFloat(std::log(0.3), std::log(20))));
            break;
        case 4:
            m_F = TO_FP(0.018);
            m_k = TO_FP(0.045);
            m_scale = TO_FP(std::exp(randomFloat(std::log(0.3), std::log(20))));
            break;
        case 5:
            m_F = TO_FP(0.010);
            m_k = TO_FP(0.033);
            m_scale = TO_FP(std::exp(randomFloat(std::log(0.3), std::log(20))));
            break;

        // sometimes end quickly on smaller panels
        case 6:
            m_F = TO_FP(0.014);
            m_k = TO_FP(0.041);
            m_scale = TO_FP(std::exp(randomFloat(std::log(0.3), std::log(20))));
            break;
        case 7:
            m_F = TO_FP(0.006);
            m_k = TO_FP(0.045);
            m_scale = TO_FP(std::exp(randomFloat(std::log(0.6), std::log(10))));
            break;
        case 8:
            m_F = TO_FP(0.010);
            m_k = TO_FP(0.047);
            m_scale = TO_FP(std::exp(randomFloat(std::log(0.3), std::log(20))));
            break;
        // case 9:
        //     m_F = TO_FP(0.006);
        //     m_k = TO_FP(0.043);
        //     m_scale = TO_FP(std::exp(randomFloat(std::log(0.6), std::log(6))));
        //     break;
    }

    m_du = 0.08 * m_scale;
    m_dv = 0.04 * m_scale;
    m_dt = 1 / m_scale;

    std::cout << "GrayScott with param set #" << m_settings["params"] <<
        std::setprecision(4) << " F=" << m_F << " k=" << m_k << " scale=" << m_scale << std::endl;
}

void GrayScottDrawer::draw(int* colIndices) {
    Drawer::draw(colIndices);

    float zoom = 1;
    size_t speed = m_settings["speed"] * FROM_FP(m_scale);

    size_t n = m_width * m_height * 2;
    for (size_t f = 0; f < speed; ++f) {
        size_t qOffset = m_q * m_width * m_height;
        size_t qOffsetNext = (!m_q) * m_width * m_height;

        for (size_t x = 0; x < m_width; ++x) {
            for (size_t y = 0; y < m_height; ++y) {
                size_t index = x + y * m_width + qOffset;
                size_t nextIndex = x + y * m_width + qOffsetNext;
                size_t left = (index - 1 + n) % n;
                size_t right = (index + 1) % n;
                size_t top = (index - m_width + n) % n;
                size_t bottom = (index + m_width) % n;

                const int &u = m_u[index];
                const int &v = m_v[index];
                int d2 = FROM_FP(FROM_FP(u * v) * v);

                int d2u = m_u[left] + m_u[right] + m_u[top] + m_u[bottom] - 4 * u;
                int d2v = m_v[left] + m_v[right] + m_v[top] + m_v[bottom] - 4 * v;
                
                // diffusion
                m_u[nextIndex] = u + FROM_FP(FROM_FP(m_dt * m_du) * d2u);
                m_v[nextIndex] = v + FROM_FP(FROM_FP(m_dt * m_dv) * d2v);

                // reaction
                m_u[nextIndex] += FROM_FP(m_dt * (-d2 + FROM_FP(m_F * (TO_FP(1.0) - u))));
                m_v[nextIndex] += FROM_FP(m_dt * (d2 - FROM_FP((m_F + m_k) * v)));
            }
        }
        m_q = !m_q;
    }

    size_t qOffset = m_q * m_width * m_height;
    int minv = TO_FP(100), maxv = TO_FP(0);
    for (size_t i = qOffset; i < qOffset + m_width * m_height; ++i) {
        const int& v = m_v[i];
        minv = std::min(minv, v);
        maxv = std::max(maxv, v);
    }
    maxv = m_lastMaxV + MAX_ROLLING_MULTIPLIER * (maxv - m_lastMaxV); // adapted from rolling EMA equation
    //std::cout << "maxv=" << std::setprecision(3) << maxv << " ";

    for (size_t x = 0; x < m_width; ++x) {
        for (size_t y = 0; y < m_height; ++y) {
            size_t x2 = x * zoom;
            size_t y2 = y * zoom;
            int v = m_v[x2 + y2 * m_width + qOffset];

            v = mapValue(v, minv, maxv, minv, TO_FP(1.0));
            colIndices[x + y * m_width] = FP_TO_FLOAT(v) * (m_palSize - 1);
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

