#ifndef DRAWER_H
#define DRAWER_H

#include <map>
#include <string>

using namespace std;


class Drawer {
public:
	Drawer(string name) : m_name(name) {}

	string name() { return m_name; }
	map<string,int>& settings() { return m_settings; }
	const map< string,pair<int,int> >& settingsRanges() { return m_settingsRanges; }
	void setSettings(const map<string,int>& settings) { m_settings = settings; }

	virtual void reset() = 0;
	virtual void draw(int width, int height, int palSize, int* colIndices) = 0;
	virtual ~Drawer() {}
	
protected:
	string m_name;
	map<string,int> m_settings;
	map< string,pair<int,int> > m_settingsRanges;
};

#endif
