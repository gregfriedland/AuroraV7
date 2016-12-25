#include <map>
#include <vector>

#include "GrayScott.h"
#include "Drawer.h"
#include "Util.h"
#include <algorithm>

#define MAX_ROLLING_MULTIPLIER (2.0 / (35 * 5 + 1))
#define NUM_INIT_ISLANDS 5
#define ISLAND_SIZE 20
#define MAX_SPEED 40 // determined empirically to allow 30fps

#ifdef __arm__
    #define vmul(x, y) vmulq_f32(x, y)
    #define vadd(x, y) vaddq_f32(x, y)
    #define vsub(x, y) vsubq_f32(x, y)
    #define vdup(x) vdupq_n_f32(x)
    #define vld(x) vld1q_f32(x)
    #define vst(x, y) vst1q_f32(x, y)

    #define vprint(name, v) { GSType arr[VEC_N]; vst1q_f32(arr, v); std::cout << name << ": "; for (size_t i=0; i < VEC_N; ++i) { std::cout << arr[i] << " "; }; std::cout << std::endl; }
#endif

GrayScottDrawer::GrayScottDrawer(int width, int height, int palSize)
: Drawer("GrayScott", width, height, palSize), m_colorIndex(0) {
    m_settings.insert(std::make_pair("speed",10));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("params",1));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(5,10)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,0)));
    m_settingsRanges.insert(std::make_pair("params", std::make_pair(0,8)));

    for (size_t q = 0; q < 2; ++q) {
        m_u[q] = new Array2D<GSType>(width, height);
        m_v[q] = new Array2D<GSType>(width, height);
    }

    m_q = true;

    m_lastMaxV = 0.5;
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
            m_u[q]->get(i) = 1.0;
            m_v[q]->get(i) = 0.0;
        }
    }

    for (size_t i = 0; i < NUM_INIT_ISLANDS; ++i) {
        size_t ix = random2() % (m_width - ISLAND_SIZE);
        size_t iy = random2() % (m_height - ISLAND_SIZE);
        for (size_t x = ix; x < ix + ISLAND_SIZE; ++x) {
            for (size_t y = iy; y < iy + ISLAND_SIZE; ++y) {
                size_t index = x + y * m_width;
                m_u[m_q]->get(index) = 0.5;
                m_v[m_q]->get(index) = 0.25;
            }
        }
    }

    // params from http://mrob.com/pub/comp/xmorphia
    GSType F, k, scale;
    switch(m_settings["params"]) {
        case 0:
            F = 0.022;
            k = 0.049;
            scale = std::exp(randomFloat(std::log(0.5), std::log(20)));
            break;
        case 1:
            F = 0.026;
            k = 0.051;
            scale = std::exp(randomFloat(std::log(0.5), std::log(20)));
            break;
        case 2:
            F = 0.026;
            k = 0.052;
            scale = std::exp(randomFloat(std::log(0.5), std::log(20)));
            break;
        case 3:
            F = 0.022;
            k = 0.048;
            scale = std::exp(randomFloat(std::log(0.5), std::log(20)));
            break;
        case 4:
            F = 0.018;
            k = 0.045;
            scale = std::exp(randomFloat(std::log(0.5), std::log(20)));
            break;
        case 5:
            F = 0.010;
            k = 0.033;
            scale = std::exp(randomFloat(std::log(0.5), std::log(20)));
            break;

        // sometimes end quickly on smaller panels
        case 6:
            F = 0.014;
            k = 0.041;
            scale = std::exp(randomFloat(std::log(0.5), std::log(5)));
            break;
        case 7:
            F = 0.006;
            k = 0.045;
            scale = std::exp(randomFloat(std::log(0.6), std::log(5)));
            break;
        case 8:
            F = 0.010;
            k = 0.047;
            scale = std::exp(randomFloat(std::log(0.5), std::log(5)));
            break;
        // case 9:
        //     m_F = 0.006;
        //     m_k = 0.043;
        //     m_scale = std::exp(randomFloat(std::log(0.6), std::log(6)));
        //     break;
    }

    m_scale = scale;
    m_du = 0.08 * m_scale;
    m_dv = 0.04 * m_scale;
    m_dt = 1 / m_scale;
    m_F = F;
    m_k = k;
    m_speed = std::min((size_t)MAX_SPEED, (size_t)(m_settings["speed"] * m_scale));

    std::cout << "GrayScott with param set #" << m_settings["params"] <<
      std::setprecision(4) << " F=" << F << " k=" << k << " scale=" << m_scale <<
      " total speed=" << m_speed << std::endl;
}

#ifdef __arm__

template <bool CHECK_BOUNDS>
inline
GSTypeN laplacian(const Array2D<GSType> *arr, int x, int y, const GSTypeN& curr) {
  const GSType* raw = arr->rawData();
  size_t w = arr->width();
  size_t h = arr->height();
  size_t index = x + y * w;
  const GSType* pos = raw + index;
  
  GSTypeN left, right, top, bottom;
  GSTypeN fourN = vdup(4);

  if (CHECK_BOUNDS) {
    GSTypeN sum;
    left = vld(raw + y * w + (x - 1 + w) % w);
    right = vld(raw + y * w + (x + 1) % w);
    top = vld(raw + ((y - 1 + h) % h) * w + x);
    bottom = vld(raw + ((y + 1) % h) * w + x);

    sum = vadd(left, right);
    sum = vadd(sum, bottom);
    sum = vadd(sum, top);
    sum = vsub(sum, vmul(curr, fourN));
    return sum;
  } else {
    GSTypeN sum;
    left = vld(pos - 1);
    right = vld(pos + 1);
    top = vld(pos - w);
    bottom = vld(pos + w);

    sum = vadd(left, right);
    sum = vadd(sum, bottom);
    sum = vadd(sum, top);
    sum = vsub(sum, vmul(curr, fourN));
    return sum;
  }
}

template <bool CHECK_BOUNDS>
inline
void updateUV(Array2D<GSType> *u[], Array2D<GSType> *v[],
						bool q, size_t x, size_t y,
						const GSTypeN& dt, const GSTypeN& du,
						const GSTypeN& dv, const GSTypeN& F,
						const GSTypeN& F_k) {
  const GSType* uIn = u[q]->rawData();
  const GSType* vIn = v[q]->rawData();
  GSType* uOut = u[1-q]->rawData();
  GSType* vOut = v[1-q]->rawData();

  size_t index = y * u[q]->width() + x;
  GSTypeN currU = vld(uIn + index);
  GSTypeN currV = vld(vIn + index);
  GSTypeN oneN = vdup(1);

  // get vector of floats for laplacian transform
  GSTypeN d2u = laplacian<CHECK_BOUNDS>(u[q], x, y, currU);
  GSTypeN d2v = laplacian<CHECK_BOUNDS>(v[q], x, y, currV);
  
  // uvv = u*v*v
  GSTypeN uvv = vmul(currU, vmul(currV, currV));
  
  // uOut[curr] = u + dt * du * d2u;
  // uOut[curr] += dt * (-d2 + F * (1 - u));
  GSTypeN uRD = vadd(currU, vmul(vmul(dt, du), d2u));
  uRD = vadd(uRD, vmul(dt, vsub(vmul(F, vsub(oneN, currU)), uvv)));
  vst(uOut + index, uRD);
  
  // vOut[curr] = v + dt * dv * d2v;
  // vOut[curr] += dt * (d2 - (F + k) * v);
  GSTypeN vRD = vadd(currV, vmul(vmul(dt, dv), d2v));
  vRD = vadd(vRD, vmul(dt, vsub(uvv, vmul(F_k, currV))));
  vst(vOut + index, vRD);
}


void GrayScottDrawer::draw(int* colIndices) {
    Drawer::draw(colIndices);

    GSType zoom = 1;

    GSTypeN dt = vdup(m_dt);
    GSTypeN du = vdup(m_du);
    GSTypeN dv = vdup(m_dv);
    GSTypeN F = vdup(m_F);
    GSTypeN F_k = vadd(F, vdup(m_k));
    
    for (size_t f = 0; f < m_speed; ++f) {
      //      	std::cout << *m_v[m_q] << std::endl;

      for (size_t y = 1; y < m_height - 1; ++y) {
            for (size_t x = VEC_N; x < m_width - VEC_N; x += VEC_N) {
	      updateUV<false>(m_u, m_v, m_q, x, y, dt, du, dv, F, F_k);
            }
        }

	// borders are a special case
        for (size_t y = 0; y < m_height; y += m_height - 1) {
  	    for (size_t x = 0; x < m_width; x += VEC_N) {
	      updateUV<true>(m_u, m_v, m_q, x, y, dt, du, dv, F, F_k);
	    }
        }
        for (size_t y = 0; y < m_height; y += 1) {
  	    for (size_t x = 0; x < m_width; x += m_width - VEC_N) {
	      updateUV<true>(m_u, m_v, m_q, x, y, dt, du, dv, F, F_k);
	    }
        }

	m_q = 1 - m_q;
    }
#else
void GrayScottDrawer::draw(int* colIndices) {
    Drawer::draw(colIndices);

    GSType zoom = 1;

    for (size_t f = 0; f < m_speed; ++f) {

      auto& uIn = *m_u[m_q];
        auto& vIn = *m_v[m_q];
        auto& uOut = *m_u[1-m_q];
        auto& vOut = *m_v[1-m_q];
        for (size_t y = 0; y < m_height; ++y) {
            for (size_t x = 0; x < m_width; ++x) {
                size_t curr = x + y * m_width;
                size_t left = (x - 1 + m_width) % m_width + y * m_width;
                size_t right = (x + 1) % m_width + y * m_width;
                size_t top = x + ((y - 1 + m_width) % m_height) * m_width;
                size_t bottom = x + ((y + 1) % m_height) * m_width;

                const GSType &u = uIn[curr];
                const GSType &v = vIn[curr];
                GSType d2 = u * v * v;

                GSType d2u = uIn[left] + uIn[right] + uIn[top] + uIn[bottom] - 4 * u;
                GSType d2v = vIn[left] + vIn[right] + vIn[top] + vIn[bottom] - 4 * v;

                // diffusion
                uOut[curr] = u + m_dt * m_du * d2u;
                vOut[curr] = v + m_dt * m_dv * d2v;

                // reaction
                uOut[curr] += m_dt * (-d2 + m_F * (1 - u));
                vOut[curr] += m_dt * (d2 - (m_F + m_k) * v);
            }
        }

        m_q = 1 - m_q;
    }
#endif
    
    GSType maxv = 0;
    for (size_t y = 0; y < m_height; ++y) {
      for (size_t x = 0; x < m_width; x += VEC_N) {
	size_t index = y * m_width + x;
	maxv = std::max(maxv, m_v[m_q]->get(index));
      }
    }
    maxv = m_lastMaxV + MAX_ROLLING_MULTIPLIER * (maxv - m_lastMaxV); // adapted from rolling EMA equation

    for (size_t y = 0; y < m_height; ++y) {
        for (size_t x = 0; x < m_width; ++x) {
	  size_t index = x + y * m_width;
	  GSType v = mapValue(m_v[m_q]->get(index), 0.0, maxv, 0.0, 1.0);
	  colIndices[index] = v * (m_palSize - 1);
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
