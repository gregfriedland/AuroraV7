#include <map>
#include <vector>

#include "GrayScott.h"
#include "Drawer.h"
#include "Util.h"
#include <algorithm>

#define MAX_ROLLING_MULTIPLIER (2.0 / (35 * 5 + 1))
#define NUM_INIT_ISLANDS 5
#define ISLAND_SIZE 20

// #define FIXED_PT_SHIFT 10
// #define TO_FP(f) ((GSType)(f * (1<<FIXED_PT_SHIFT)))
// #define FROM_FP(i) (i >> FIXED_PT_SHIFT)
// #define FP_TO_FLOAT(i) ((float)(i>>FIXED_PT_SHIFT))
#define TO_FP(f) f
#define FROM_FP(i) i


GrayScottDrawer::GrayScottDrawer(int width, int height, int palSize, Camera* camera)
: Drawer("GrayScott", width, height, palSize), m_colorIndex(0), m_camera(camera) {
    m_settings.insert(std::make_pair("speed",10));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("params",1));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(10,10)));//5,25)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,0)));//,10)));
    m_settingsRanges.insert(std::make_pair("params", std::make_pair(0,0)));//8)));

    for (size_t q = 0; q < 2; ++q) {
        m_u[q] = new Array2D<GSType>(width, height);
        m_v[q] = new Array2D<GSType>(width, height);
    }
    m_q = true;

    m_lastMaxV = TO_FP(0.5);
    reset();
}

GrayScottDrawer::~GrayScottDrawer() {
    for (size_t q = 0; q < 2; ++q) {
        delete[] m_u[q];
        delete[] m_v[q];
    }
}

void GrayScottDrawer::reset() {
    for (size_t q = 0; q < 2; ++q) {
        for (size_t i = 0; i < m_width * m_height; ++i) {
            m_u[q]->get(i) = TO_FP(1.0);
            m_v[q]->get(i) = TO_FP(0.0);
        }
    }

    for (size_t i = 0; i < NUM_INIT_ISLANDS; ++i) {
        size_t ix = random2() % (m_width - ISLAND_SIZE);
        size_t iy = random2() % (m_height - ISLAND_SIZE);
        for (size_t x = ix; x < ix + ISLAND_SIZE; ++x) {
            for (size_t y = iy; y < iy + ISLAND_SIZE; ++y) {
                size_t index = x + y * m_width;
                m_u[m_q]->get(index) = TO_FP(0.5);
                m_v[m_q]->get(index) = TO_FP(0.25);
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
        //     m_F = 0.006;
        //     m_k = 0.043;
        //     m_scale = std::exp(randomFloat(std::log(0.6), std::log(6)));
        //     break;
    }

    m_du = 0.08 * m_scale;
    m_dv = 0.04 * m_scale;
    m_dt = 1 / m_scale;

    std::cout << "GrayScott with param set #" << m_settings["params"] <<
        std::setprecision(4) << " F=" << m_F << " k=" << m_k << " scale=" << m_scale << std::endl;
}

inline void diffuseReact(const Array2D<GSType>& uIn, const Array2D<GSType>& vIn, Array2D<GSType>& uOut, Array2D<GSType>& vOut,
                         GSType dt, GSType du, GSType dv, GSType F, GSType k, size_t curr, size_t left, size_t right, size_t top, size_t bottom) {
    const GSType &u = uIn[curr];
    const GSType &v = vIn[curr];
    GSType d2 = u * v * v;

    GSType d2u = uIn[left] + uIn[right] + uIn[top] + uIn[bottom] - 4 * u;
    GSType d2v = vIn[left] + vIn[right] + vIn[top] + vIn[bottom] - 4 * v;

    // diffusion
    uOut[curr] = u + FROM_FP(FROM_FP(dt * du) * d2u);
    vOut[curr] = v + FROM_FP(FROM_FP(dt * dv) * d2v);

    // reaction
    uOut[curr] += FROM_FP(dt * (-d2 + FROM_FP(F * (1 - u))));
    vOut[curr] += dt * (d2 - FROM_FP((F + k) * v));
}

void GrayScottDrawer::draw(int* colIndices) {
    Drawer::draw(colIndices);

    GSType zoom = 1;
    size_t speed = m_settings["speed"];//m_scale;

    size_t n = m_width * m_height * 2;
    for (size_t f = 0; f < speed; ++f) {
        // add neighbors for borders
        for (size_t y = 0; y < m_height; y += m_height - 1) {
            for (size_t x = 0; x < m_width; x += m_width - 1) {
                size_t curr = x + y * m_width;
                size_t left = (x - 1 + m_width) % m_width + y * m_width;
                size_t right = (x + 1) % m_width + y * m_width;
                size_t top = x + ((y - 1 + m_width) % m_height) * m_width;
                size_t bottom = x + ((y + 1) % m_height) * m_width;

                diffuseReact(*m_u[m_q], *m_v[m_q], *m_u[1-m_q], *m_u[1-m_q], m_dt, m_du, m_dv, m_F, m_k,
                    curr, left, right, top, bottom);
            }
        }
        // add neighbors for center
        for (size_t y = 1; y < m_height - 1; ++y) {
            size_t baseInd = y * m_width;
            for (size_t x = 1; x < m_width - 1; ++x) {
                size_t curr = x + baseInd;
                size_t left = curr - 1;
                size_t right = curr + 1;
                size_t top = curr - m_width;
                size_t bottom = curr + m_width;

                diffuseReact(*m_u[m_q], *m_v[m_q], *m_u[1-m_q], *m_u[1-m_q], m_dt, m_du, m_dv, m_F, m_k,
                    curr, left, right, top, bottom);
            }
        }

        m_q = !m_q;
    }

    GSType minv = TO_FP(100), maxv = TO_FP(0);
    for (size_t i = 0; i < m_width * m_height; ++i) {
        const GSType& v = m_v[m_q]->get(i);
        minv = std::min(minv, v);
        maxv = std::max(maxv, v);
    }
    maxv = m_lastMaxV + MAX_ROLLING_MULTIPLIER * (maxv - m_lastMaxV); // adapted from rolling EMA equation
    //std::cout << "maxv=" << std::setprecision(3) << maxv << " ";

    for (size_t y = 0; y < m_height; ++y) {
        for (size_t x = 0; x < m_width; ++x) {
            size_t x2 = x * zoom;
            size_t y2 = y * zoom;
            GSType v = m_v[m_q]->get(x2 + y2 * m_width);

            v = mapValue(v, minv, maxv, minv, TO_FP(1.0));
            colIndices[x + y * m_width] = v * (m_palSize - 1);
        }
    }

    for (size_t x = 0; x < m_width; ++x) {
        for (size_t y = 0; y < m_height; ++y) {
            colIndices[x + y * m_width] += m_colorIndex;
        }
    }
    m_colorIndex += m_settings["colorSpeed"];
    m_lastMaxV = maxv;
}
