#include "Controller.h"
#include "Palette.h"
#include "AlienBlob.h"
#include "Bzr.h"
#include "Off.h"
#include "Util.h"
#include <iostream>
#include <uv.h>
#include <stdlib.h>


void Controller::init()
{
	// create drawers and set start drawer
	m_drawers.insert(make_pair("AlienBlob", new AlienBlobDrawer(m_width, m_height, m_palSize)));
	m_drawers.insert(make_pair("Bzr", new BzrDrawer(m_width, m_height, m_palSize)));
	m_drawers.insert(make_pair("Off", new OffDrawer(m_width, m_height, m_palSize)));
	changeDrawer({m_startDrawerName});

	// create serial connection
	if (m_device.size() > 0)
		m_serial.connect();

	// start camera

	// start face detection
}


void Controller::start() {
	uv_timer_init(uv_default_loop(), &m_timer);
	m_timer.data = this;
	uv_timer_start(&m_timer, timer_cb, 0, 1000 / m_fps);
}

void Controller::stop() {
	uv_timer_stop(&m_timer);
	if (m_device.size() > 0)
		m_serial.close();
}

void Controller::loop() {
	m_fpsCounter.tick();

	// update camera if appropriate

	// update facedetection if appropriate

	// change drawer every so often
	if (m_drawerChangeTimer.tick(NULL))
		changeDrawer({"Bzr", "AlienBlob"});

	// update drawer
	m_currDrawer->draw(m_colIndices);

	// pack data for serial transmission
	int i = 0;
	for (int y = 0; y < m_height; y++) {
		for (int x = 0; x < m_width; x++) {
			Color24 col = m_palettes.get(m_currPalIndex, m_colIndices[x + y * m_width]);
			// if (x == 0 && y == 0)
			// 	cout << "00 index=" << m_colIndices[x + y * m_width] << " rgb=" << (int)col.r << " " << (int)col.g << " " << (int)col.b << endl;
			m_serialWriteBuffer[i++] = min((unsigned char)254, col.r);
			m_serialWriteBuffer[i++] = min((unsigned char)254, col.g);
			m_serialWriteBuffer[i++] = min((unsigned char)254, col.b);
		}
	}
	m_serialWriteBuffer[i++] = 255;

	// send serial data
	if (m_device.size() > 0) {
		m_serial.write(m_serialWriteBuffer, m_serialWriteBufferSize);

		unsigned char buffer[256];
		if (m_serial.read(256, buffer) > 0)
	        cout << "read: " << (int) buffer[0] << endl;
	}
}


const map<string,int>& Controller::settings() {
	return m_currDrawer->settings();
}

const map< string,pair<int,int> >& Controller::settingsRanges() {
	return m_currDrawer->settingsRanges();
}

void Controller::setSettings(const map<string,int>& settings) {
	m_currDrawer->setSettings(settings);
    m_drawerChangeTimer.reset();
}

string Controller::currDrawerName() {
	return m_currDrawer->name();
}

vector<string> Controller::drawerNames() {
	vector<string> names;
	for (auto& d: m_drawers)
		names.push_back(d.first);
	return names;
}

void Controller::changeDrawer(vector<string> names) {
	string name;
	assert(names.size() > 0);
	if (names.size() == 1)
		name = names[0];
	else
		name = names[random2() % names.size()];

    if (m_drawers.find(name) == m_drawers.end()) {
    	cout << "Invalid drawer name: " << name << endl;
    	return;
    }

    cout << "Changing to drawer: " << name << endl;
    m_currDrawer = m_drawers[name];
    randomizeSettings();
    m_currDrawer->reset();

    m_drawerChangeTimer.reset();
}

void Controller::randomizeSettings() {
	auto& settings = m_currDrawer->settings();
	auto& settingsRanges = m_currDrawer->settingsRanges();

    for (auto& setting: settings) {
    	auto& range = settingsRanges.find(setting.first)->second;
    	setting.second = random2() % (range.second - range.first + 1) + range.first;
    } 

    m_currPalIndex = random2() % m_palettes.size();
    m_currDrawer->reset();
    m_drawerChangeTimer.reset();
}
