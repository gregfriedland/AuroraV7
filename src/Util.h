#ifndef UTIL_H
#define UTIL_H

#include <iostream>
#include <iomanip>
#include <sys/time.h>
// #include <chrono>
#include <random>

using namespace std;
// using namespace std::chrono;


struct Color24 {
    Color24(int col) 
    : r((col >> 16) & 255), g((col >> 8) & 255), b(col & 255)
    {}

    Color24(unsigned char _r, unsigned char _g, unsigned char _b)
    : r(_r), g(_g), b(_b)
    {}

    unsigned char r, g, b;
};


inline unsigned long millis() {
	struct timeval tv;

	gettimeofday(&tv, NULL);

	return (unsigned long)(tv.tv_sec) * 1000 +
    	   (unsigned long)(tv.tv_usec) / 1000;
	// return duration_cast< milliseconds >(
 //    	system_clock::now().time_since_epoch()).count();
}


static minstd_rand0 randGen(millis());
inline int random2() {
	return randGen();
}


class IntervalTimer {
public:
	IntervalTimer(unsigned int interval) 
	: m_lastTime(millis()), m_interval(interval) 
	{}

	void reset() {
		m_lastTime = millis();
	}

	bool tick(unsigned int* timeLeft) {
		unsigned long currTime = millis();
		if (timeLeft != NULL)
			*timeLeft = std::max(0, (int)currTime - (int)(m_lastTime + m_interval));
		//cout << "currTime:" << currTime << " lastTime:" << m_lastTime << endl;
		if (currTime - m_lastTime > m_interval) {
			m_lastTime = currTime;
			return true;
		} else
			return false;
	}

private:
	unsigned long m_lastTime;
	unsigned int m_interval;
};


class FpsCounter {
public:
	FpsCounter(unsigned int outputInterval, string name)
	: m_count(0), m_lastTime(millis()), m_interval(outputInterval), m_name(name)
	{}

	void tick() {
		m_count++;
		unsigned int currTime = millis();
		if (currTime - m_lastTime > m_interval) {
			float fps = 1000. * m_count/(currTime - m_lastTime);
	        cout << m_name << ": " << fixed << setprecision(1) << fps << "fps\n";
			m_lastTime = currTime;
			m_count = 0;
		}
	}

private:
	unsigned int m_count;
	unsigned long m_lastTime;
	unsigned int m_interval;
	string m_name;
};

#endif