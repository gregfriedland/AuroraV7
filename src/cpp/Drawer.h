#ifndef DRAWER_H
#define DRAWER_H

#include "Util.h"
#include <map>
#include <string>


class Drawer {
public:
	Drawer(std::string name, int width, int height, int palSize) 
	: m_name(name), m_width(width), m_height(height), m_palSize(palSize), m_frame(0)
	{}

	std::string name() { return m_name; }
	std::map<std::string,int>& settings() { return m_settings; }
	const std::map<std::string,std::pair<int,int> >& settingsRanges() { return m_settingsRanges; }
	void setSettings(const std::map<std::string,int>& settings) { m_settings = settings; }

	void randomizeSettings() {
	    auto& settings = this->settings();
	    auto& settingsRanges = this->settingsRanges();

	    for (auto& setting: settings) {
  	        auto& range = settingsRanges.find(setting.first)->second;
		setting.second = random2() % (range.second - range.first + 1) + range.first;
	    } 

	    reset();
	}

	void setPaused(bool value) { m_paused = value; }
	bool isPaused() const { return m_paused; }
	
	virtual void cleanup() {}
	virtual void reset() = 0;

	virtual void draw(int* colIndices) {
		++m_frame;
	}

	virtual ~Drawer() {}
	
protected:
	std::string m_name;
	int m_width, m_height, m_palSize;
	std::map<std::string,int> m_settings;
	std::map<std::string,std::pair<int,int>> m_settingsRanges;
	bool m_paused;
	size_t m_frame;
};

#endif
