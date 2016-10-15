#include "Controller.h"
#include "Palette.h"
#include "AlienBlob.h"
#include "Bzr.h"
#include "Off.h"
#include "Video.h"
#include "Util.h"
#include <iostream>
#include <uv.h>
#include <stdlib.h>


static void timer_cb(uv_timer_t* handle) {
    ((Controller*)handle->data)->loop();
}

Controller::Controller(Matrix* matrix, int width, int height, int palSize,
    int* baseColors, int numBaseColors, int baseColorsPerPalette,
    bool layoutLeftToRight, string startDrawerName,
    int drawerChangeInterval, Camera* camera, FaceDetect* faceDetect)
: m_matrix(matrix), m_width(width), m_height(height), m_palSize(palSize),
  m_layoutLeftToRight(layoutLeftToRight),
  m_startDrawerName(startDrawerName), 
  m_palettes(palSize, baseColors, numBaseColors, baseColorsPerPalette),
  m_camera(camera), m_faceDetect(faceDetect),
  m_currDrawer(NULL), m_drawerChangeTimer(drawerChangeInterval),
  m_fpsCounter(5000, "Controller")
{
    m_currPalIndex = random2() % m_palettes.size();

    m_colIndicesSize = width * height;
    m_colIndices = new int[m_colIndicesSize];
    init();
}

Controller::~Controller() {
    cout << "Freeing Controller memory\n";

    for (auto elem: m_drawers)
        delete elem.second;
    delete m_colIndices;
}

const unsigned char* Controller::rawData(size_t& size) {
    return m_matrix->rawData(size);
}

void Controller::init()
{
	// create drawers and set start drawer
	m_drawers.insert(make_pair("AlienBlob", new AlienBlobDrawer(m_width, m_height, m_palSize, m_camera)));
	m_drawers.insert(make_pair("Bzr", new BzrDrawer(m_width, m_height, m_palSize, m_camera)));
    if (m_camera != NULL)
        m_drawers.insert(make_pair("Video", new VideoDrawer(m_width, m_height, m_palSize, m_camera)));
	m_drawers.insert(make_pair("Off", new OffDrawer(m_width, m_height, m_palSize)));
    if (m_drawers.find(m_startDrawerName) != m_drawers.end())
        changeDrawer({m_startDrawerName});
    else
        changeDrawer({"AlienBlob"});
}

// void Controller::start(int interval) {
// 	// uv_timer_init(uv_default_loop(), &m_timer);
// 	// m_timer.data = this;
// 	// uv_timer_start(&m_timer, timer_cb, 0, interval);
// }

// void Controller::stop() {
// 	// uv_timer_stop(&m_timer);
// }

void Controller::loop() {
	m_fpsCounter.tick();

    // change to Video drawer if faces have been detected or change
    // from video drawer is no faces detected
    if (m_faceDetect != NULL && m_faceDetect->status() && m_currDrawer->name().compare("Off") != 0 &&
        m_currDrawer->name().compare("Video") != 0) {
        changeDrawer({"Video"});
    } else if (m_faceDetect != NULL && !m_faceDetect->status() && m_currDrawer->name().compare("Video") == 0) {
        changeDrawer({"Bzr", "AlienBlob"});
    }

	// Change drawer every so often, but only to video if faces were detected
	if (m_drawerChangeTimer.tick(NULL)) {
        if (m_currDrawer->name().compare("Video") == 0)
            randomizeSettings();
        else
            changeDrawer({"Bzr", "AlienBlob"});
    }

	// update drawer
	m_currDrawer->draw(m_colIndices);

	for (int y = 0; y < m_height; y++) {
		for (int x = 0; x < m_width; x++) {
			Color24 col = m_palettes.get(m_currPalIndex, m_colIndices[x + y * m_width]);
            m_matrix->setPixel(x, y, col.r, col.g, col.b);
		}
	}
    m_matrix->update();
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
