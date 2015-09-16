#ifndef DRAWER_H
#define DRAWER_H

#include <map>
#include <string>

using namespace std;


class Drawer {
public:
	Drawer(string name, int width, int height, int palSize) 
	: m_name(name), m_width(width), m_height(height), m_palSize(palSize)
	{}

	string name() { return m_name; }
	map<string,int>& settings() { return m_settings; }
	const map< string,pair<int,int> >& settingsRanges() { return m_settingsRanges; }
	void setSettings(const map<string,int>& settings) { m_settings = settings; }

	virtual void reset() = 0;
	virtual void draw(int* colIndices) = 0;
	virtual ~Drawer() {}
	
protected:
	string m_name;
	int m_width, m_height, m_palSize;
	map<string,int> m_settings;
	map< string,pair<int,int> > m_settingsRanges;
};

#endif
