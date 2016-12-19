#include <map>
#include <vector>

#include "Bzr.h"
#include "Drawer.h"
#include "Util.h"

#define BZR_SPEED_MULTIPLIER 100
#define DIFFUSION_NUM_CELLS 1
#define MIN_WIDTH 128
#define MIN_HEIGHT 64

void bzr(int width, int height, int numColors, int bzrWidth, int bzrHeight, int& state, int numStates,
         int& p, int& q, float zoom, float *a, float *b, float *c, int *indices);


BzrDrawer::BzrDrawer(int width, int height, int palSize, Camera* camera)
: Drawer("Bzr", width, height, palSize), m_colorIndex(0), m_camera(camera) {
    m_settings.insert(std::make_pair("speed",50));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("zoom",70));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(95,95)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,0)));
    m_settingsRanges.insert(std::make_pair("zoom", std::make_pair(MIN_WIDTH / width * 100 / 4, MIN_WIDTH / width * 100)));

    m_bzrWidth = std::max(MIN_WIDTH, m_width);
    m_bzrHeight = std::max(MIN_HEIGHT, m_height);

    m_p = 0;
    m_q = 1;
    m_state = 0;
    m_a = new float[m_bzrWidth * m_bzrHeight * 2];
    m_b = new float[m_bzrWidth * m_bzrHeight * 2];
    m_c = new float[m_bzrWidth * m_bzrHeight * 2];

    reset();
}

BzrDrawer::~BzrDrawer() {
    delete m_a;
    delete m_b;
    delete m_c;
}

void BzrDrawer::reset() {
    for (int x = 0; x < m_bzrWidth; x++)
        for (int y = 0; y < m_bzrHeight; y++) {
            int index = x + y * m_bzrWidth;
            m_a[index] = (random2() % 10000) / 10000.0;
            m_b[index] = (random2() % 10000) / 10000.0;
            m_c[index] = (random2() % 10000) / 10000.0;
        }
}

void BzrDrawer::draw(int* colIndices) {
    float speed = m_settings["speed"]/100.0;
    //float speed = min(100.0, m_settings["speed"]/100.0 * (1 + m_camera->diff()));

    int numStates = BZR_SPEED_MULTIPLIER - floor(pow(speed, 0.25) * (BZR_SPEED_MULTIPLIER-1));

    bzr(m_width, m_height, m_palSize, m_bzrWidth, m_bzrHeight, m_state, numStates, m_p, m_q, 
        m_settings["zoom"]/100.0, m_a, m_b, m_c, colIndices);

    for (int x = 0; x < m_width; x++)
        for (int y = 0; y < m_height; y++)
            colIndices[x + y * m_width] += m_colorIndex;

    m_colorIndex += m_settings["colorSpeed"];
}


void bzr(int screenWidth, int screenHeight, int numColors, int bzrWidth, int bzrHeight, int& state, int numStates,
         int& p, int& q, float zoom, float *a, float *b, float *c, int *indices) {
    if (state > numStates)
        state = 1;

    int quotient = (2*DIFFUSION_NUM_CELLS+1) * (2*DIFFUSION_NUM_CELLS+1);
    float invQuotient = 1.0 / quotient;
    if (state == 1) {
        for (int x=0; x<bzrWidth; x++) {
            for (int y=0; y<bzrHeight; y++) {
                float c_a=0, c_b=0, c_c=0;

                int n = p * bzrWidth * bzrHeight;
                for (int j=y-DIFFUSION_NUM_CELLS; j<=y+DIFFUSION_NUM_CELLS; j++) {
                    int jj = (j + bzrHeight) % bzrHeight;
                    int jjwn = jj * bzrWidth + n;
                    for (int i=x-DIFFUSION_NUM_CELLS; i<=x+DIFFUSION_NUM_CELLS; i++) {
                        int ii = (i + bzrWidth) % bzrWidth;

                        int ind = ii + jjwn;
                        c_a += a[ind];
                        c_b += b[ind];
                        c_c += c[ind];
                    }
                }

                c_a *= invQuotient;
                c_b *= invQuotient;
                c_c *= invQuotient;

                int ind = x + y * bzrWidth + q * bzrWidth * bzrHeight;
                a[ind] = std::min(std::max(c_a + c_a * ( c_b - c_c ), 0.0f), 1.0f);
                b[ind] = std::min(std::max(c_b + c_b * ( c_c - c_a ), 0.0f), 1.0f);
                c[ind] = std::min(std::max(c_c + c_c * ( c_a - c_b ), 0.0f), 1.0f);
            }
        }
        p = 1-p;
        q = 1-q;
    }
  
    for (int x=0; x<screenWidth; x++) {
        for (int y=0; y<screenHeight; y++) {
            int x2 = x * zoom;
            int y2 = y * zoom;
            const float& a_p = a[x2 + y2*bzrWidth + bzrWidth*bzrHeight*p];
            const float& a_q = a[x2 + y2*bzrWidth + bzrWidth*bzrHeight*q];
      
            // interpolate
            float a_val = state * (a_p - a_q) / numStates + a_q;
            indices[x + y * screenWidth] = a_val * (numColors-1);
        }
    }
    state++;  
}
