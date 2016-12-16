#include <map>
#include <vector>

#include "GrayScott.h"
#include "Drawer.h"
#include "Util.h"

// #define GRAY_SCOTT_SPEED_MULTIPLIER 100
#define NUM_INIT_ISLANDS 1
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
    m_dt = 2; //0.1;
    m_rxn = 0.62;

    m_u = new float[m_width * m_height * 2];
    m_v = new float[m_width * m_height * 2];
    m_q = true;

    reset();
}

GrayScottDrawer::~GrayScottDrawer() {
    delete[] m_u;
    delete[] m_v;
}

float& GrayScottDrawer::u(int x, int y, bool q) {
    if (q) {
        return m_u[x + y * m_width];
    } else {
        return m_u[x + y * m_width + m_width * m_height];
    }
}

float& GrayScottDrawer::v(int x, int y, bool q) {
    if (q) {
        return m_v[x + y * m_width];
    } else {
        return m_v[x + y * m_width + m_width * m_height];
    }
}

void GrayScottDrawer::reset() {
    for (int q = 0; q < 2; ++q) {
        for (int x = 0; x < m_width; ++x) {
            for (int y = 0; y < m_height; ++y) {
                int index = x + y * m_width;
                u(x, y, q) = 1.0;
                v(x, y, q) = 0.0;
            }
        }

        for (int i = 0; i < NUM_INIT_ISLANDS; ++i) {
            int ix = 1;//random2() % (m_width - ISLAND_SIZE);
            int iy = 1;//random2() % (m_height - ISLAND_SIZE);
            for (int x = ix; x < ix + ISLAND_SIZE; ++x) {
                for (int y = iy; y < iy + ISLAND_SIZE; ++y) {
                    u(x, y, q) = 0.5;//(random2() % 10000) / 10000.0;
                    v(x, y, q) = 0.25;//(random2() % 10000) / 10000.0;
                }
            }
        }
    }
}

void GrayScottDrawer::draw(int* colIndices) {
    float zoom = 1; //m_settings["zoom"] / 100.0;

    for (int x = 1; x < m_width - 1; ++x) {
        for (int y = 1; y < m_height - 1; ++y) {
            float uu = u(x,y,m_q);
            float vv = v(x,y,m_q);
            float d2 = uu * vv * vv;
            float dx2 = m_dx * m_dx;

            float d2u = u(x-1,y,m_q) + u(x+1,y,m_q) + u(x,y-1,m_q) + u(x,y+1,m_q) - 4 * uu;
            float d2v = v(x-1,y,m_q) + v(x+1,y,m_q) + v(x,y-1,m_q) + v(x,y+1,m_q) - 4 * vv;
            
            // if (x == 2 && y == 2) {
            //     // std::cout <<  std::endl;
            //     // std::cout << "dx2=" << dx2 << std::endl;
            //     std::cout << "uu=" << uu << " vv=" << vv << " d2u=" << d2u << " d2v=" << d2v << " d2=" << d2 << std::endl;
            // }
 
            // GrayScot.java
            // nextU = max(0, currU + t * ((dU * ((uu[right] + uu[left] + uu[bottom] + uu[top]) - 4 * currU) - d2) + currF * (1.0f - currU)));
            // nextV = max(0, currV + t * ((dV * ((vv[right] + vv[left] + vv[bottom] + vv[top]) - 4 * currV) + d2) - currK * currV));
            
            // diffusion
            u(x,y,!m_q) = uu + m_dt * m_du / dx2 * d2u;
            v(x,y,!m_q) = vv + m_dt * m_dv / dx2 * d2v;

            // reaction
            u(x,y,!m_q) += m_dt * m_rxn * (-d2 + m_F * (1 - uu));
            v(x,y,!m_q) += m_dt * m_rxn * (d2 - (m_F + m_k) * vv);

            // u(x,y,!m_q) = uu + m_du * m_dt / dx2 * d2u;// ;
            // v(x,y,!m_q) = vv + m_dv * m_dt / dx2 * d2v;//(m_dv + d2vdx2 + d2 - (m_k + m_F) * vv);

            // if (x == 1 && y == 1) {
            //     std::cout << "post-diff: uu=" << u(x,y,!m_q) << " vv=" << v(x,y,!m_q) << std::endl;
            // }
            
            // u(x,y,!m_q) += m_dt * (-d2 + m_F * (1 - uu));
            // v(x,y,!m_q) += m_dt * (d2 - (/*m_F +*/ m_k) * vv);

            // if (x == 1 && y == 1) {
            //     std::cout << "post-rxn: uu=" << u(x,y,!m_q) << " vv=" << v(x,y,!m_q) << std::endl;
            //     std::cout << std::endl;
            // }
        }
    }

    m_q = !m_q;

    for (int x = 0; x < m_width; ++x) {
        for (int y = 0; y < m_height; ++y) {
            int x2 = x * zoom;
            int y2 = y * zoom;

            colIndices[x + y * m_width] = v(x2,y2,m_q) * (m_palSize - 1);
        }
    }

    // for (int x = 0; x < m_width; ++x) {
    //     for (int y = 0; y < m_height; ++y) {
    //         colIndices[x + y * m_width] += m_colorIndex;
    //     }
    // }

    // m_colorIndex += m_settings["colorSpeed"];
}

