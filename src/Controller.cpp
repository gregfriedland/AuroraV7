#include "Controller.h"
#include "Palette.h"
#include "AlienBlob.h"
#include "Util.h"
#include <iostream>
#include <uv.h>

void Controller::init()
{
	// create drawers and set start drawer
	//m_drawers.emplace("Bzr", BzrDrawer());

	m_drawers.insert(make_pair("AlienBlob", new AlienBlobDrawer()));
	m_currDrawer = m_drawers[m_startDrawerName];

	// create serial connection
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
}

void Controller::loop() {
	//cout << "Controller::loop\n";

	// update camera if appropriate

	// update facedetection if appropriate

	// change drawer if appropriate

	// update drawer
	m_currDrawer->draw(m_width, m_height, m_palSize, m_colIndices);

	// pack data for serial transmission
	int i = 0;
	for (int x = 0; x < m_width; x++) {
		for (int y = 0; y < m_height; y++) {
			Color24 col = m_palettes.get(m_palIndex, m_colIndices[x + y * m_width]);
			m_serialWriteBuffer[i++] = col.r;
			m_serialWriteBuffer[i++] = col.g;
			m_serialWriteBuffer[i++] = col.b;
		}
	}

	// send serial data
	m_serial.write(m_serialWriteBuffer, m_serialWriteBufferSize);
}


map<string,int>
Controller::getSettings() {
}

map< string,pair<int,int> >
Controller::getSettingsRanges() {
}

void Controller::setSettings(const map<string,int>& settings) {
}

string Controller::getCurrDrawerName() {
	m_currDrawer->name();
}

vector<string> Controller::getDrawerNames() {
}

void Controller::changeDrawer(string name) {
}

void Controller::randomizeSettings() {
}