#include <map>
#include <vector>

#include "GrayScott.h"
#include <algorithm>

#define MAX_ROLLING_MULTIPLIER (2.0 / (35 * 5 + 1))
#define NUM_INIT_ISLANDS 5
#define ISLAND_SIZE 20
#define MAX_SPEED 40 // determined empirically to allow 30fps


template <bool CHECK_BOUNDS>
class GrayScottUVUpdater : public UVUpdater<CHECK_BOUNDS> {
public:    
    GrayScottUVUpdater(float dt, float du, float dv, float F, float k) {
        setParams(dt, du, dv, F, k);
    }

    void setParams(float dt, float du, float dv, float F, float k) {
        m_dt = RD_DUP(dt);
        // std::cout << "m_dt=" << m_dt << std::endl;
        m_du = RD_DUP(du);
        m_dv = RD_DUP(dv);
        m_F = RD_DUP(F);
        m_k = RD_DUP(k);
        m_Fk = RD_ADD(m_F, m_k);        
    }

    virtual void operator()(Array2D<float> *u[], Array2D<float> *v[],
                            size_t q, size_t x, size_t y) {
        const float* uIn = u[q]->rawData();
        const float* vIn = v[q]->rawData();
        float* uOut = u[1-q]->rawData();
        float* vOut = v[1-q]->rawData();

        size_t index = y * u[q]->width() + x;
        RDType currU = RD_LOAD(uIn + index);
        RDType currV = RD_LOAD(vIn + index);
        RDType one = RD_DUP(1);

        // get vector of floats for laplacian transform
        RDType d2u = this->laplacian(u[q], x, y);
        RDType d2v = this->laplacian(v[q], x, y);

        // uvv = u*v*v
        RDType uvv = RD_MUL(currU, RD_MUL(currV, currV));

        // uOut[curr] = u + dt * du * d2u;
        // uOut[curr] += dt * (-d2 + F * (1 - u));
        RDType uRD = RD_ADD(currU, RD_MUL(RD_MUL(m_dt, m_du), d2u));
        uRD = RD_ADD(uRD, RD_MUL(m_dt, RD_SUB(RD_MUL(m_F, RD_SUB(one, currU)), uvv)));
        RD_STORE(uOut + index, uRD);

        // vOut[curr] = v + dt * dv * d2v;
        // vOut[curr] += dt * (d2 - (F + k) * v);
        RDType vRD = RD_ADD(currV, RD_MUL(RD_MUL(m_dt, m_dv), d2v));
        vRD = RD_ADD(vRD, RD_MUL(m_dt, RD_SUB(uvv, RD_MUL(m_Fk, currV))));
        RD_STORE(vOut + index, vRD);

        // std::cout << "x=" << x << " y=" << y << " m_dt=" << m_dt << " m_F=" << m_F << " m_Fk=" << m_Fk << 
        //     " d2u=" << d2u << " d2v=" << d2v <<
        //     " uvv=" << uvv << " uRD=" << uRD << " vRD=" << vRD << std::endl;
    }

 private:
    RDType m_dt, m_du, m_dv, m_F, m_k, m_Fk;    
};


GrayScottDrawer::GrayScottDrawer(int width, int height, int palSize, FindBeats* findBeats)
: ReactionDiffusionDrawer("GrayScott", width, height, palSize, findBeats) {
    m_colorIndex = 0;
    m_settings.insert(std::make_pair("speed",10));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("params",1));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(5,10)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(5,15)));
    // Skip param sets 6-8 on small panels (they end quickly)
    int maxParams = (width < 64 || height < 64) ? 5 : 8;
    m_settingsRanges.insert(std::make_pair("params", std::make_pair(0, maxParams)));

    reset();
}

void GrayScottDrawer::reset() {
    ReactionDiffusionDrawer::resetToValues(1.0, 0, 0.5, 0.25);
    setParams();
}

void GrayScottDrawer::setParams() {
    // params from http://mrob.com/pub/comp/xmorphia
    float F, k, scale;
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
            scale = std::exp(randomFloat(std::log(0.5), std::log(10)));
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
            scale = std::exp(randomFloat(std::log(1.0), std::log(5)));
            break;
        case 8:
            F = 0.010;
            k = 0.047;
            scale = std::exp(randomFloat(std::log(1.0), std::log(5)));
            break;
        // case 9:
        //     m_F = 0.006;
        //     m_k = 0.043;
        //     m_scale = std::exp(randomFloat(std::log(0.6), std::log(6)));
        //     break;
    }

    m_scale = scale;
    float du = 0.08 * m_scale;
    float dv = 0.04 * m_scale;
    float dt = 1.0 / m_scale;
    m_speed = std::min((size_t)MAX_SPEED, (size_t)(m_settings["speed"] * m_scale));

    std::cout << "GrayScott with param set #" << m_settings["params"] <<
      std::setprecision(4) << " F=" << F << " k=" << k << " scale=" << m_scale <<
      " totalspeed=" << m_speed << " dt=" << dt << std::endl;

    if (m_uvUpdaterBorder == nullptr) {
        m_uvUpdaterBorder = new GrayScottUVUpdater<true>(dt, du, dv, F, k);
    } else {
        dynamic_cast<GrayScottUVUpdater<true>*>(m_uvUpdaterBorder)->setParams(dt, du, dv, F, k);
    }

    if (m_uvUpdaterInternal == nullptr) {
        m_uvUpdaterInternal = new GrayScottUVUpdater<false>(dt, du, dv, F, k);
    } else {
        dynamic_cast<GrayScottUVUpdater<false>*>(m_uvUpdaterInternal)->setParams(dt, du, dv, F, k);
    }
}
