#ifndef UTIL_H
#define UTIL_H

#include <iostream>
#include <iomanip>
#include <functional>
#include <chrono>
#include <random>
#include <array>

using namespace std::chrono;


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
	/* struct timeval tv; */

	/* gettimeofday(&tv, NULL); */

	/* return (unsigned long)(tv.tv_sec) * 1000 + */
    /* 	   (unsigned long)(tv.tv_usec) / 1000; */
	return duration_cast< milliseconds >(
    	system_clock::now().time_since_epoch()).count();
}

static unsigned long int startTime = millis();
inline void fail() {
    std::cout << "Exit after " << ((millis() - startTime) / 1000) << "s\n";
    exit(1);
}

static std::minstd_rand0 randGen(millis());
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
	FpsCounter(unsigned int outputInterval, const std::string& name);
	void tick();

private:
	unsigned int m_count;
	unsigned long m_lastTime;
	unsigned int m_interval;
	std::string m_name;
};


class FrameTimer {
public:
    FrameTimer();
    void tick(unsigned int intervalMs, std::function<void()> func);

private:
    unsigned long m_lastTime;
};
#endif
