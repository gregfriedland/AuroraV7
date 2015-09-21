#include "Util.h"

FpsCounter::FpsCounter(unsigned int outputInterval, string name)
  : m_count(0), m_lastTime(millis()), m_interval(outputInterval), m_name(name)
{}

void FpsCounter::tick() {
    m_count++;
    unsigned long currTime = millis();
    if (currTime - m_lastTime > m_interval) {
        cout << "currTime=" << currTime << " lastTime=" << m_lastTime << " interval=" << m_interval << " count=" << m_count << endl;
        float fps = 1000. * m_count/(currTime - m_lastTime);
        cout << m_name << ": " << fixed << setprecision(1) << fps << "fps\n";
        m_lastTime = currTime;
        m_count = 0;
    }
}
