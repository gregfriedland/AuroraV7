#ifndef UTIL_H
#define UTIL_H

#include <iostream>
#include <iomanip>
#include <functional>
#include <chrono>
#include <random>
#include <array>
#include <cassert>
#include <ostream>
#include <sstream>

using namespace std::chrono;


inline std::string hexToBytes(const std::string& hex) {
  std::string bytes;

  for (unsigned int i = 0; i < hex.length(); i += 2) {
    std::string byteString = hex.substr(i, 2);
    char byte = (char) strtol(byteString.c_str(), NULL, 16);
    bytes.push_back(byte);
  }

  return bytes;
}


inline std::string bytesToHex(const std::string& bytes) {
	std::stringstream ss;
	ss << std::hex << std::setfill('0');
	for (int i = 0; i < 32; ++i)
	{
	    ss << std::setw(2) << static_cast<unsigned>(bytes[i]);
	}
	return ss.str();
}

struct Color24 {
    Color24(int col) 
    : r((col >> 16) & 255), g((col >> 8) & 255), b(col & 255)
    {}

    Color24(unsigned char _r, unsigned char _g, unsigned char _b)
    : r(_r), g(_g), b(_b)
    {}

    unsigned char r, g, b;
};


inline float mapValue(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

inline int mapValue(int x, int in_min, int in_max, int out_min, int out_max) {
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

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

inline float randomFloat(float min, float max) {
	static std::random_device rd;
	static std::mt19937 gen(rd());

	return std::uniform_real_distribution<>(min, max)(gen);
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


#if 0
template <typename T>
void convolve(const Array2D<T>* convArr, const Array2D<T>* inputArr, Array2D<T>* outputArr) {
	assert(inputArr->width() == outputArr->width() && inputArr->height() == outputArr->height());

	int xConvMid = convArr->width() / 2;
	int yConvMid = convArr->height() / 2;
	T convSum = convArr->sum();

	for (int x = 0; x < inputArr->width(); ++x) {
		for (int y = 0; y < inputArr->height(); ++y) {

			T val = 0;
			for (int yy = 0; yy < convArr->height(); ++yy) {
				for (int xx = 0; xx < convArr->width(); ++xx) {
					val += convArr->get(xx, yy) * inputArr->get(x + xx - xConvMid, y + yy - yConvMid);
					// if (x == 0 && y == 0) {
					// 	std::cout << xx << "/" << yy << "=" << convArr->get(xx,yy) << " " << 
					// 		x + xx - xConvMid << "/" << y + yy - yConvMid << "=" << inputArr->get(x - xx - xConvMid, y - yy - yConvMid) << std::endl;
					// }
				}
			}
			val /= convSum;
			outputArr->get(x, y) = val;
		}
	}
}
#endif

#endif
