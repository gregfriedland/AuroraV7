#ifndef REACTIONDIFFUSION_H
#define REACTIONDIFFUSION_H

#include "Drawer.h"
#include "Util.h"
#include "Array2D.h"
#include "FindBeats.h"
#include <sstream>
#include <ostream>

#ifdef __arm__
    #include <arm_neon.h>
    using RDType = float32x4_t;
    #define RDTYPE_N 4

    inline std::ostream& operator<<(std::ostream& os, const RDType& val) {
        float arr[RDTYPE_N];
        vst1q_f32(arr, val);
        for (size_t i=0; i < RDTYPE_N; ++i) {
            os << arr[i] << " ";
        }
        return os;
    }

    #define RD_MUL(x, y) vmulq_f32(x, y)
    #define RD_ADD(x, y) vaddq_f32(x, y)
    #define RD_SUB(x, y) vsubq_f32(x, y)
    #define RD_MAX(x, y) vmaxq_f32(x, y)
    #define RD_MIN(x, y) vminq_f32(x, y)
    #define RD_DUP(x) vdupq_n_f32(x)
    #define RD_LOAD(x) vld1q_f32(x)
    #define RD_STORE(x, y) vst1q_f32(x, y)
#else
    using RDType = float;
    #define RDTYPE_N 1

    #define RD_MUL(x, y) (x * y)
    #define RD_ADD(x, y) (x + y)
    #define RD_SUB(x, y) (x - y)
    #define RD_MAX(x, y) std::max(x, y)
    #define RD_MIN(x, y) std::min(x, y)
    #define RD_DUP(x) (x)
    #define RD_LOAD(x) ((x)[0])
    #define RD_STORE(x, y) (x)[0] = y
#endif


template <bool CHECK_BOUNDS>
class UVUpdater {
public:
    virtual ~UVUpdater() {}
    virtual void operator()(Array2D<float> *u[], Array2D<float> *v[],
               size_t q, size_t x, size_t y) = 0;

    inline RDType laplacian(const Array2D<float> *arr, int x, int y);
};


class ReactionDiffusionDrawer : public Drawer {
public:
    ReactionDiffusionDrawer(const std::string& name, int width, int height, int palSize, FindBeats* findBeats);

    virtual ~ReactionDiffusionDrawer();

    virtual void reset() = 0;

    virtual void draw(int* colIndices);

protected:
    virtual void setParams() = 0;
    virtual void resetToValues(float bgU, float bgV, float fgU, float fgV);
    virtual void resetRandom(float low, float high);

    Array2D<float> *m_u[2], *m_v[2];
    size_t m_q;
    size_t m_colorIndex;
    size_t m_speed;
    float m_lastMaxV;
    float m_scale;
    UVUpdater<false>* m_uvUpdaterInternal;
    UVUpdater<true>* m_uvUpdaterBorder;
    FindBeats* m_findBeats;
};


template <bool CHECK_BOUNDS>
RDType UVUpdater<CHECK_BOUNDS>::laplacian(const Array2D<float> *arr, int x, int y) {
  const float* raw = arr->rawData();
  size_t w = arr->width();
  size_t h = arr->height();
  size_t index = x + y * w;
  const float* pos = raw + index;
  
  RDType left, right, top, bottom, sum;
  RDType curr = RD_LOAD(pos);
  RDType four = RD_DUP(4);

  if (CHECK_BOUNDS) {
    left = RD_LOAD(raw + y * w + (x - 1 + w) % w);
    right = RD_LOAD(raw + y * w + (x + 1) % w);
    top = RD_LOAD(raw + ((y - 1 + h) % h) * w + x);
    bottom = RD_LOAD(raw + ((y + 1) % h) * w + x);

    sum = RD_ADD(left, right);
    sum = RD_ADD(sum, bottom);
    sum = RD_ADD(sum, top);
    sum = RD_SUB(sum, RD_MUL(curr, four));
  } else {
    left = RD_LOAD(pos - 1);
    right = RD_LOAD(pos + 1);
    top = RD_LOAD(pos - w);
    bottom = RD_LOAD(pos + w);

    sum = RD_ADD(left, right);
    sum = RD_ADD(sum, bottom);
    sum = RD_ADD(sum, top);
    sum = RD_SUB(sum, RD_MUL(curr, four));
  }
  // std::cout << "raw=" << raw << " pos=" << pos << " pos-1=" << (pos - 1) << std::endl;
  // std::cout << "x=" << x << " y=" << y << " left=" << toString(left) << " right=" << toString(right) << 
  //   " top=" << toString(top) << " bottom=" << toString(bottom) << " curr=" <<
  //   toString(curr) << " sum=" << sum << std::endl;
  return sum;
}

#endif
