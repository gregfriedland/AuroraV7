#include <map>
#include <vector>

#include "Bzr.h"
#include "Drawer.h"
#include "Util.h"

#define BZR_SPEED_MULTIPLIER 100

void bzr(int width, int height, int numColors, int width2, int height2, int& state, int numStates,
         int& p, int& q, float zoom, float *a, float *b, float *c, int *indices);


BzrDrawer::BzrDrawer(int width, int height, int palSize, Camera* camera)
: Drawer("Bzr", width, height, palSize), m_colorIndex(0), m_camera(camera) {
    m_settings.insert(std::make_pair("speed",50));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("zoom",70));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(0,100)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,50)));
    m_settingsRanges.insert(std::make_pair("zoom", std::make_pair(30,100)));

    m_p = 0;
    m_q = 1;
    m_state = 0;
    m_a = new float[m_width * m_height * 2];
    m_b = new float[m_width * m_height * 2];
    m_c = new float[m_width * m_height * 2];

    reset();
}

BzrDrawer::~BzrDrawer() {
    delete m_a;
    delete m_b;
    delete m_c;
}

void BzrDrawer::reset() {
    for (int x = 0; x < m_width; x++)
        for (int y = 0; y < m_height; y++) {
            int index = x + y * m_width;
            m_a[index] = (random2() % 10000) / 10000.0;
            m_b[index] = (random2() % 10000) / 10000.0;
            m_c[index] = (random2() % 10000) / 10000.0;
        }
}

void BzrDrawer::draw(int* colIndices) {
    float speed = m_settings["speed"]/100.0;
    //float speed = min(100.0, m_settings["speed"]/100.0 * (1 + m_camera->diff()));

    int numStates = BZR_SPEED_MULTIPLIER - floor(pow(speed, 0.25) * (BZR_SPEED_MULTIPLIER-1));

    bzr(m_width, m_height, m_palSize, m_width, m_height, m_state, numStates, m_p, m_q, 
        m_settings["zoom"]/100.0, m_a, m_b, m_c, colIndices);

    for (int x = 0; x < m_width; x++)
        for (int y = 0; y < m_height; y++)
            colIndices[x + y * m_width] += m_colorIndex;

    m_colorIndex += m_settings["colorSpeed"];
}


void bzr(int width, int height, int numColors, int width2, int height2, int& state, int numStates,
         int& p, int& q, float zoom, float *a, float *b, float *c, int *indices) {
  if (state > numStates)
    state = 1;

  if (state == 1) {
    for (int x=0; x<width2; x++) {
      for (int y=0; y<height2; y++) {
        float c_a=0, c_b=0, c_c=0;

        for (int i=x-1; i<=x+1; i++) {
          int ii = (i + width2) % width2;
          for (int j=y-1; j<=y+1; j++) {
            int jj = (j + height2) % height2;
            int ind = ii + jj * width2 + p * width2 * height2;
            c_a += a[ind];
            c_b += b[ind];
            c_c += c[ind];
          }
        }

        c_a /= 9;
        c_b /= 9;
        c_c /= 9;

        int ind = x + y * width2 + q * width2 * height2;
        a[ind] = std::min(std::max(c_a + c_a * ( c_b - c_c ), 0.0f), 1.0f);
        b[ind] = std::min(std::max(c_b + c_b * ( c_c - c_a ), 0.0f), 1.0f);
        c[ind] = std::min(std::max(c_c + c_c * ( c_a - c_b ), 0.0f), 1.0f);
      }
    }
    p = 1-p;
    q = 1-q;
  }
  
  for (int x=0; x<width; x++) {
    for (int y=0; y<height; y++) {
      int x2 = x * zoom;
      int y2 = y * zoom;
      float a_p = a[x2 + y2*width2 + width2*height2*p];
      float a_q = a[x2 + y2*width2 + width2*height2*q];
      
      // interpolate
      float a_val = state * (a_p - a_q) / numStates + a_q;
//      if (x == 0 && y ==0) {
//        printf("%d: %.2f -> (%.2f) -> %.2f", state, a_q, a_val, a_p);
//      }
      indices[x + y * width] = a_val * (numColors-1);
    }
  }
  state++;  
}
