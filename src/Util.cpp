#include "Util.h"

FpsCounter::FpsCounter(unsigned int outputInterval, const std::string& name)
  : m_count(0), m_lastTime(millis()), m_interval(outputInterval), m_name(name)
{}

void FpsCounter::tick() {
    m_count++;
    unsigned long currTime = millis();
    if (currTime - m_lastTime > m_interval) {
        //cout << "currTime=" << currTime << " lastTime=" << m_lastTime << " interval=" << m_interval << " count=" << m_count << endl;
        float fps = 1000. * m_count / (currTime - m_lastTime);
        std::cout << m_name << ": " << std::fixed << std::setprecision(1) << fps << "fps\n";
        m_lastTime = currTime;
        m_count = 0;
    }
}

FrameTimer::FrameTimer()
  : m_lastTime(millis())
{}

void FrameTimer::tick(unsigned int intervalMs, std::function<void()> func) {
    unsigned long currTime = millis();
    if (currTime - m_lastTime >= intervalMs) {
        // std::cout << currTime - m_lastTime << " " << intervalMs << std::endl;
        func();
        m_lastTime = currTime;
    }
}