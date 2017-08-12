#include <map>
#include <vector>

#include "GinzburgLandau.h"
#include <algorithm>

#define MAX_ROLLING_MULTIPLIER (2.0 / (35 * 5 + 1))
#define NUM_INIT_ISLANDS 5
#define ISLAND_SIZE 20
#define MAX_SPEED 7 // determined empirically to allow 30fps


template <bool CHECK_BOUNDS>
class GinzburgLandauUVUpdater : public UVUpdater<CHECK_BOUNDS> {
public:    
    GinzburgLandauUVUpdater(float dt, float du, float dv, float alpha, float beta, float gamma, float delta) {
        setParams(dt, du, dv, alpha, beta, gamma, delta);
    }

    void setParams(float dt, float du, float dv, float alpha, float beta, float gamma, float delta) {
        m_dt = RD_DUP(dt);
        // std::cout << "m_dt=" << m_dt << std::endl;
        m_du = RD_DUP(du);
        m_dv = RD_DUP(dv);
        m_alpha = RD_DUP(alpha);
        m_negBeta = RD_DUP(-beta);
        m_gamma = RD_DUP(gamma);
        m_delta = RD_DUP(gamma);
    }

    virtual void operator()(Array2D<float> *u[], Array2D<float> *v[],
                            size_t q, size_t x, size_t y) {
        // From equation in Ready
        // delta_a = D_a * laplacian_a + alpha*a - gamma*b + (-beta*a + delta*b)*(a*a+b*b);
        // delta_b = D_b * laplacian_b + alpha*b + gamma*a + (-beta*b - delta*a)*(a*a+b*b);

        const float* uIn = u[q]->rawData();
        const float* vIn = v[q]->rawData();
        float* uOut = u[1-q]->rawData();
        float* vOut = v[1-q]->rawData();

        size_t index = y * u[q]->width() + x;
        RDType currU = RD_LOAD(uIn + index);
        RDType currV = RD_LOAD(vIn + index);

        // get vector of floats for laplacian transform
        RDType d2u = this->laplacian(u[q], x, y);
        RDType d2v = this->laplacian(v[q], x, y);

        RDType uuvv = RD_ADD(RD_MUL(currU, currU), RD_MUL(currV, currV));

        RDType uRD = RD_SUB(RD_ADD(RD_MUL(m_du, d2u), RD_MUL(m_alpha, currU)), RD_MUL(m_gamma, currV));
	uRD = RD_ADD(uRD, RD_MUL(RD_ADD(RD_MUL(m_delta, currV), RD_MUL(m_negBeta, currU)), uuvv));
	uRD = RD_ADD(currU, RD_MUL(m_dt, uRD));
	RD_STORE(uOut + index, uRD);
	
        RDType vRD = RD_ADD(RD_ADD(RD_MUL(m_dv, d2v), RD_MUL(m_alpha, currV)), RD_MUL(m_gamma, currU));
	vRD = RD_ADD(vRD, RD_MUL(RD_SUB(RD_MUL(m_negBeta, currV), RD_MUL(m_delta, currU)), uuvv));
	vRD = RD_ADD(currV, RD_MUL(m_dt, vRD));
	RD_STORE(vOut + index, vRD);
    }

 private:
    RDType m_dt, m_du, m_dv, m_alpha, m_negBeta, m_gamma, m_delta;
};


GinzburgLandauDrawer::GinzburgLandauDrawer(int width, int height, int palSize, FindBeats* findBeats)
: ReactionDiffusionDrawer("GinzburgLandau", width, height, palSize, findBeats) {
    m_colorIndex = 0;
    m_settings.insert(std::make_pair("speed",10));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("params",1));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(5,10)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,0)));
    m_settingsRanges.insert(std::make_pair("params", std::make_pair(1,1)));
}

void GinzburgLandauDrawer::reset() {
    // ReactionDiffusionDrawer::resetToValues(0, 1, 0.5, 0.25);
    ReactionDiffusionDrawer::resetRandom(-0.25, 0.25);
    setParams();
}

void GinzburgLandauDrawer::setParams() {
    float alpha, beta, gamma, delta, scale;
    switch(m_settings["params"]) {
        case 0:
            alpha = 0.0625;
            beta = 1;
            gamma = 0.0625;
            delta = 1;
            scale = 1; //std::exp(randomFloat(std::log(0.5), std::log(20)));
            break;
        case 1:
            alpha = 0.0625;
            beta = 1;
            gamma = 0.0625;
            delta = 1;
            scale = std::exp(randomFloat(std::log(0.5), std::log(20)));
            break;
    }

    m_scale = scale;
    float du = 0.2 * m_scale;
    float dv = 0.2 * m_scale;
    float dt = 0.2 / m_scale;
    m_speed = std::min((size_t)MAX_SPEED, (size_t)(m_settings["speed"] * m_scale));

    std::cout << "GinzburgLandau with param set #" << m_settings["params"] <<
      std::setprecision(4) << " alpha=" << alpha << " beta=" << beta << " gamma=" << gamma <<
      " delta=" << delta << " scale=" << m_scale << " totalspeed=" << m_speed << " dt=" << dt << std::endl;

    if (m_uvUpdaterBorder == nullptr) {
        m_uvUpdaterBorder = new GinzburgLandauUVUpdater<true>(dt, du, dv, alpha, beta, gamma, delta);
    } else {
        dynamic_cast<GinzburgLandauUVUpdater<true>*>(m_uvUpdaterBorder)->setParams(dt, du, dv, alpha, beta, gamma, delta);
    }

    if (m_uvUpdaterInternal == nullptr) {
        m_uvUpdaterInternal = new GinzburgLandauUVUpdater<false>(dt, du, dv, alpha, beta, gamma, delta);
    } else {
        dynamic_cast<GinzburgLandauUVUpdater<false>*>(m_uvUpdaterInternal)->setParams(dt, du, dv, alpha, beta, gamma, delta);
    }
}
