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


inline float mapValue(float x, float in_min, float in_max, float out_min, float out_max) {
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


template<typename T>
class Array2D {
 public:
 	Array2D(size_t width, size_t height)
 	: m_width(width), m_height(height) {
 		m_data = new T[width*height];
 	}

 	~Array2D() {
 		delete[] m_data;
 	}

 	T& get(int x, int y) {
		if (x < 0)
 			x += m_width;
 		else if (x >= m_width)
 			x -= m_width;

 		if (y < 0)
 			y += m_height;
 		else if (y >= m_height)
 			y -= m_height;

 		return m_data[x + y * m_width];
  	}

 	const T& get(int x, int y) const {
		if (x < 0)
 			x += m_width;
 		else if (x >= m_width)
 			x -= m_width;

 		if (y < 0)
 			y += m_height;
 		else if (y >= m_height)
 			y -= m_height;

 		return m_data[x + y * m_width];
  	}

 	T& operator[](size_t index) {
 		return m_data[index];
 	}

 	const T& operator[](size_t index) const {
 		return m_data[index];
 	}

 	void random() {
 		for (size_t x = 0; x < m_width; ++x) {
 			for (size_t y = 0; y < m_height; ++y) {
 				get(x, y) = (random2() % 10000) / 10000.0;
 			}
 		}
 	}

 	T sum() const {
 		T sum = 0;
 		for (size_t x = 0; x < m_width; ++x) {
 			for (size_t y = 0; y < m_height; ++y) {
 				sum += get(x, y);
 			}
 		}
 		return sum;
 	}

 	void constrain(T min, T max) {
 		for (size_t x = 0; x < m_width; ++x) {
 			for (size_t y = 0; y < m_height; ++y) {
 				get(x, y) = std::min(min, std::max(max, get(x, y)));
 			}
 		}
 	}

 	const T* rawData() const {
 		return m_data;
 	}

 	size_t width() const {
 		return m_width;
 	}

 	size_t height() const {
 		return m_height;
 	}

	friend std::ostream& operator <<(std::ostream& os, const Array2D<T>& arr) {
 		for (size_t x = 0; x < arr.m_width; ++x) {
 			for (size_t y = 0; y < arr.m_height; ++y) {
 				os << std::setprecision(3) << std::setw(4) << arr.get(x, y) << " ";
 			}
 			os << std::endl;
 		}
 		return os;
	}
	
 private:
 	size_t m_width, m_height;
 	T* m_data;
};

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
