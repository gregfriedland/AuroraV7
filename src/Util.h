#ifndef UTIL_H
#define UTIL_H

// #include <chrono>
#include <iostream>
#include <sys/time.h>

using namespace std;
// using namespace std::chrono;


inline unsigned long millis() {
	struct timeval tv;

	gettimeofday(&tv, NULL);

	return (unsigned long)(tv.tv_sec) * 1000 +
    	   (unsigned long)(tv.tv_usec) / 1000;
	// return duration_cast< milliseconds >(
 //    	system_clock::now().time_since_epoch()).count();
}


class IntervalTimer {
public:
	IntervalTimer(unsigned int interval) 
	: m_lastTime(millis()), m_interval(interval) 
	{}

	bool tick(unsigned int& timeLeft) {
		unsigned int currTime = millis();
		timeLeft = std::max(0, (int)currTime - (int)(m_lastTime + m_interval));
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
	        cout << m_name << ": " << (1000 * m_count/(currTime - m_lastTime)) << "fps\n";
			m_lastTime = currTime;
		}
	}

private:
	unsigned int m_count;
	unsigned long m_lastTime;
	unsigned int m_interval;
	string m_name;
};

#endif