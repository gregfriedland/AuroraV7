#include <map>
#include <vector>

#include "GrayScott.h"
#include "Drawer.h"
#include "Util.h"
#include <algorithm>

#define MAX_ROLLING_MULTIPLIER (2.0 / (35 * 5 + 1))
#define NUM_INIT_ISLANDS 1
#define ISLAND_SIZE 10

#ifdef __arm__
    #define vmul(x, y) vmulq_f32(x, y)
    #define vadd(x, y) vaddq_f32(x, y)
    #define vsub(x, y) vsubq_f32(x, y)
    #define vdup(x) vdupq_n_f32(x)
    GSTypeN fourN = vdup(4);
    GSTypeN oneN = vdup(1);

#define vprint(name, v) { GSType arr[VEC_N]; vst1q_f32(arr, v); std::cout << name << ": "; for (size_t i=0; i < VEC_N; ++i) { std::cout << arr[i] << " "; }; std::cout << std::endl; }
#endif

GrayScottDrawer::GrayScottDrawer(int width, int height, int palSize, Camera* camera)
: Drawer("GrayScott", width, height, palSize), m_colorIndex(0), m_camera(camera) {
    m_settings.insert(std::make_pair("speed",10));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("params",1));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(10,10)));//5,25)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,0)));//,10)));
    m_settingsRanges.insert(std::make_pair("params", std::make_pair(0,0)));//8)));

#ifdef __arm__
    for (size_t q = 0; q < 2; ++q) {
        m_u[q] = new GSArrayType(width, height);
        m_v[q] = new GSArrayType(width, height);
    }
#else
    for (size_t q = 0; q < 2; ++q) {
        m_u[q] = new Array2D<GSType>(width, height);
        m_v[q] = new Array2D<GSType>(width, height);
    }
#endif
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
#ifdef __arm__
    for (size_t q = 0; q < 2; ++q) {
      for (size_t i = 0; i < m_width * m_height; i += VEC_N) {
            m_u[q]->setN(i, 1.0);
            m_v[q]->setN(i, 0.0);
        }
    }

    for (size_t i = 0; i < NUM_INIT_ISLANDS; ++i) {
        size_t ix = random2() % (m_width - ISLAND_SIZE);
        size_t iy = random2() % (m_height - ISLAND_SIZE);
        ix = ix - ix % VEC_N;
        iy = iy - iy % VEC_N;
	
        assert(ISLAND_SIZE % VEC_N == 0);
        for (size_t y = iy; y < iy + ISLAND_SIZE; ++y) {
	  for (size_t x = ix; x < ix + ISLAND_SIZE; x += VEC_N) {
	    size_t index = x + y * m_width;
	    m_u[m_q]->setN(index, 0.5);
	    m_v[m_q]->setN(index, 0.25);
	  }
        }
    }
#else    
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
#endif

    // params from http://mrob.com/pub/comp/xmorphia
    GSType F, k, scale;
    switch(m_settings["params"]) {
        case 0:
            F = 0.022;
            k = 0.049;
            scale = 5;//std::exp(randomFloat(std::log(0.3), std::log(20)));
            break;
        case 1:
            F = 0.026;
            k = 0.051;
            scale = std::exp(randomFloat(std::log(0.3), std::log(20)));
            break;
        case 2:
            F = 0.026;
            k = 0.052;
            scale = std::exp(randomFloat(std::log(0.3), std::log(20)));
            break;
        case 3:
            F = 0.022;
            k = 0.048;
            scale = std::exp(randomFloat(std::log(0.3), std::log(20)));
            break;
        case 4:
            F = 0.018;
            k = 0.045;
            scale = std::exp(randomFloat(std::log(0.3), std::log(20)));
            break;
        case 5:
            F = 0.010;
            k = 0.033;
            scale = std::exp(randomFloat(std::log(0.3), std::log(20)));
            break;

        // sometimes end quickly on smaller panels
        case 6:
            F = 0.014;
            k = 0.041;
            scale = std::exp(randomFloat(std::log(0.3), std::log(20)));
            break;
        case 7:
            F = 0.006;
            k = 0.045;
            scale = std::exp(randomFloat(std::log(0.6), std::log(10)));
            break;
        case 8:
            F = 0.010;
            k = 0.047;
            scale = std::exp(randomFloat(std::log(0.3), std::log(20)));
            break;
        // case 9:
        //     m_F = 0.006;
        //     m_k = 0.043;
        //     m_scale = std::exp(randomFloat(std::log(0.6), std::log(6)));
        //     break;
    }

    m_scale = scale;
    GSType du = 0.08 * m_scale;
    GSType dv = 0.04 * m_scale;
    GSType dt = 1 / m_scale;

#ifdef __arm__
    m_F = vdup(F);
    m_k = vdup(k);
    m_du = vdup(du);
    m_dv = vdup(dv);
    m_dt = vdup(dt);
#else
    m_F = F;
    m_k = k;
    m_du = du;
    m_dv = dv;
    m_dt = dt;
#endif

    std::cout << "GrayScott with param set #" << m_settings["params"] <<
        std::setprecision(4) << " F=" << F << " k=" << k << " scale=" << m_scale << std::endl;
}


#ifdef __arm__
GSTypeN laplacian(const GSArrayType& arr, size_t index, size_t width) {
    GSTypeN curr = arr.getN(index);
    GSTypeN left = arr.getN(index - 1);
    GSTypeN right = arr.getN(index + 1);
    GSTypeN bottom = arr.getN(index - width);
    GSTypeN top = arr.getN(index + width);

    GSTypeN sum = vadd(left, right);
    sum = vadd(sum, bottom);
    sum = vadd(sum, top);
    sum = vsub(sum, vmul(curr, fourN));
    return sum;
}

GSTypeN laplacianOverlap(const GSArrayType& arr, int x, int y) {
    size_t w = arr.width();
    size_t h = arr.height();

    GSTypeN curr = arr.getN<true>(y * w + x);
    GSTypeN left = arr.getN<true>(y * w + (x - 1 + w) % w);
    GSTypeN right = arr.getN<true>(y * w + (x + 1) % w);
    GSTypeN bottom = arr.getN<true>(((y - 1 + h) % h) * w + x);
    GSTypeN top = arr.getN<true>(((y + 1) % h) * w + x);

#if 0
    if (x == 0 && y == h - 1) {
      std::cout << "  left index: " << y * w + (x - 1 + w) % w << std::endl;
      vprint("  curr:", curr);
      vprint("  left:", left);
      vprint("  right:", right);
      vprint("  bottom:", bottom);
      vprint("  top:", top);
    }
#endif
    
    GSTypeN sum = vadd(left, right);
    sum = vadd(sum, bottom);
    sum = vadd(sum, top);
    sum = vsub(sum, vmul(curr, fourN));
    return sum;
}

void GrayScottDrawer::draw(int* colIndices) {
    Drawer::draw(colIndices);

    GSType zoom = 1;
    size_t speed = m_settings["speed"]; // m_scale;

    for (size_t f = 0; f < speed; ++f) {
      //	std::cout << *m_v[m_q] << std::endl;

#if 1
      for (size_t y = 1; y < m_height - 1; ++y) {
            for (size_t x = VEC_N; x < m_width - VEC_N; x += VEC_N) {
                size_t index = y * m_width + x;
                GSTypeN u = m_u[m_q]->getN(index);
                GSTypeN v = m_v[m_q]->getN(index);

                // get vector of floats for laplacian transform
                GSTypeN d2u = laplacian(*m_u[m_q], index, m_width);
                GSTypeN d2v = laplacian(*m_v[m_q], index, m_width);

                // uvv = u*v*v
                GSTypeN uvv = vmul(u, vmul(v, v));

                // uOut[curr] = u + dt * du * d2u;
                // uOut[curr] += dt * (-d2 + F * (1 - u));
                GSTypeN uRD = vadd(u, vmul(vmul(m_dt, m_du), d2u));
                uRD = vadd(uRD, vmul(m_dt, vsub(vmul(m_F, vsub(oneN, u)), uvv)));
                m_u[1-m_q]->setN(index, uRD);

                // vOut[curr] = v + dt * dv * d2v;
                // vOut[curr] += dt * (d2 - (F + k) * v);
                GSTypeN vRD = vadd(v, vmul(vmul(m_dt, m_dv), d2v));
                vRD = vadd(vRD, vmul(m_dt, vsub(uvv, vmul(vadd(m_F, m_k), v))));
                m_v[1-m_q]->setN(index, vRD);
            }
        }
#endif
#if 1
	// borders are a special case
        for (size_t y = 0; y < m_height; y += m_height - 1) {
  	    for (size_t x = 0; x < m_width; x += m_width - VEC_N) {
                size_t index = y * m_width + x;
                GSTypeN u = m_u[m_q]->getN<true>(index);
                GSTypeN v = m_v[m_q]->getN<true>(index);

                // get vector of floats for laplacian transform
                GSTypeN d2u = laplacianOverlap(*m_u[m_q], x, y);
                GSTypeN d2v = laplacianOverlap(*m_v[m_q], x, y);

                // uvv = u*v*v
                GSTypeN uvv = vmul(u, vmul(v, v));

                // uOut[curr] = u + dt * du * d2u;
                // uOut[curr] += dt * (-d2 + F * (1 - u));
                GSTypeN uRD = vadd(u, vmul(vmul(m_dt, m_du), d2u));
                uRD = vadd(uRD, vmul(m_dt, vsub(vmul(m_F, vsub(oneN, u)), uvv)));
                m_u[1-m_q]->setN(index, uRD);

                // vOut[curr] = v + dt * dv * d2v;
                // vOut[curr] += dt * (d2 - (F + k) * v);
                GSTypeN vRD = vadd(v, vmul(vmul(m_dt, m_dv), d2v));
                vRD = vadd(vRD, vmul(m_dt, vsub(uvv, vmul(vadd(m_F, m_k), v))));
                m_v[1-m_q]->setN(index, vRD);

#if 0
		for (size_t yy = 0; yy < m_height; yy += m_height - 1) {
		  if (x == 0 && y == yy) {
		    std::cout << "x==0 y==" << yy << std::endl;
		    vprint("  u", u);
		    vprint("  v", v);
		    vprint("  d2v", d2v);
		    vprint("  uvv", uvv);
		    vprint("  vRD", vRD);
		  }
		}
#endif		
	    }
        }
#endif

	m_q = 1 - m_q;

	// // set the top and bottom border equal to the overlapped values from the other side
	// // this way we don't have to do modulus ops in the main loop
	// for (size_t x = ARRAY_BORDER_W; x < arrWidth - ARRAY_BORDER_W; ++x) {
	//   size_t indexTopOut = (ARRAY_BORDER_H - 1) * arrWidth + x;
	//   size_t indexTopIn = ARRAY_BORDER_H * arrWidth + x;
	//   size_t indexBottomOut = (arrHeight - ARRAY_BORDER_H) * arrWidth + x; 
	//   size_t indexBottomIn = (arrHeight - ARRAY_BORDER_H - 1) * arrWidth + x;

	//   m_u[m_q]->setN(indexTopOut, m_u[m_q]->get(indexBottomIn));
	//   m_u[m_q]->setN(indexBottomOut, m_u[m_q]->get(indexTopIn));
	//   m_v[m_q]->setN(indexTopOut, m_v[m_q]->get(indexBottomIn));
	//   m_v[m_q]->setN(indexBottomOut, m_v[m_q]->get(indexTopIn));
	// }
	
	// for (size_t y = ARRAY_BORDER_H; y < arrHeight - ARRAY_BORDER_H; ++y) {
	//   size_t indexLeftOut = y * arrWidth + ARRAY_BORDER_W - VEC_N;
	//   size_t indexLeftIn = y * arrWidth + ARRAY_BORDER_W;
	//   size_t indexRightOut = y * arrWidth + arrWidth - ARRAY_BORDER_W;
	//   size_t indexRightIn = y * arrWidth + arrWidth - ARRAY_BORDER_W - VEC_N;

	//   m_u[m_q]->setN(indexLeftOut, m_u[m_q]->get(indexRightIn));
	//   m_u[m_q]->setN(indexRightOut, m_u[m_q]->get(indexLeftIn));
	//   m_v[m_q]->setN(indexLeftOut, m_v[m_q]->get(indexRightIn));
	//   m_v[m_q]->setN(indexRightOut, m_v[m_q]->get(indexLeftIn));
	// }
    }
#else
void GrayScottDrawer::draw(int* colIndices) {
    Drawer::draw(colIndices);

    GSType zoom = 1;
    size_t speed = m_settings["speed"] * m_scale;

    for (size_t f = 0; f < speed; ++f) {

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
    
    GSType minv = 100, maxv = 0;
    for (size_t y = 0; y < m_height; ++y) {
      for (size_t x = 0; x < m_width; ++x) {
	size_t index = y * m_width + x;
        const GSType& v = m_v[m_q]->get(index);
        minv = std::min(minv, v);
        maxv = std::max(maxv, v);
      }
    }
    maxv = m_lastMaxV + MAX_ROLLING_MULTIPLIER * (maxv - m_lastMaxV); // adapted from rolling EMA equation

    for (size_t y = 0; y < m_height; ++y) {
        for (size_t x = 0; x < m_width; ++x) {
            size_t x2 = x * zoom;
            size_t y2 = y * zoom;
            GSType v = m_v[m_q]->get(x2 + y2 * m_width);

            v = mapValue(v, minv, maxv, minv, 1.0);
	    size_t index = x + y * m_width;
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
