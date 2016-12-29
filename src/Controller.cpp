#include "Controller.h"
#include "Palette.h"
#include "AlienBlob.h"
#include "Bzr.h"
#include "GrayScott.h"
#include "Off.h"
#include "Video.h"
#include "Util.h"
#include <iostream>
#include <stdlib.h>
#include <thread>
#include <highgui.h>
#include "json.hpp"
#include <fstream>

using json = nlohmann::json;


ControllerSettings::ControllerSettings(const std::string& configFilename) {
    try {
        std::ifstream ifs(configFilename);
        json j;
        ifs >> j;

        std::string matrixType = j["matrix"];
        if (matrixType == "HzellerRpi") {
            m_matrixType = HZELLER_RPI_MATRIX;
        } else if (matrixType == "Serial") {
            m_matrixType = SERIAL_MATRIX;
        } else if (matrixType == "ComputerScreen") {
            m_matrixType = COMPUTER_SCREEN_MATRIX;
        } else if (matrixType == "Noop") {
            m_matrixType = NOOP_MATRIX;
        } else {
            std::cerr << "Invalid matrix type in json file: " << matrixType << 
                ". Must be one of: 'HzellerRpi', 'Serial', or 'Computer'" << std::endl;
            exit(1);            
        }

        m_width = j["width"];
        m_height = j["height"];
        m_gamma = j["gamma"];
        m_palSize = j["paletteSize"];
        m_fps = j["fps"];
        m_startDrawerName = j["startDrawer"];
        for (auto& d: j["drawers"]) {
            m_drawers.push_back(d);
        }
        m_drawerChangeInterval = j["drawerChangeInterval"];
        m_faceDetectFps = j["faceDetection"]["fps"];
        m_faceVideoDrawerTimeout = j["faceDetection"]["videoDrawerTimeout"];
        m_device = j["serialDevice"];

        m_cameraSettings.m_camWidth = j["camera"]["width"];
        m_cameraSettings.m_camHeight = j["camera"]["height"];
        m_cameraSettings.m_screenWidth = j["width"];
        m_cameraSettings.m_screenHeight = j["height"];
        m_cameraSettings.m_fps = j["camera"]["fps"];
    } catch(std::exception e) {
        std::cerr << "Error while parsing json config file: " << e.what() << std::endl;
        exit(1);
    }
}

Controller::Controller(Matrix* matrix, const ControllerSettings& settings, const std::vector<int>& baseColors,
                       Camera* camera, FaceDetect* faceDetect)
: m_matrix(matrix), m_settings(settings), m_camera(camera), m_faceDetect(faceDetect),
  m_palettes(m_settings.m_palSize, baseColors, m_settings.m_baseColorsPerPalette, m_settings.m_gamma),
  m_currDrawer(NULL), m_fpsCounter(2000, "Controller"),
  m_drawerChangeTimer(m_settings.m_drawerChangeInterval) {

    m_currPalIndex = random2() % m_palettes.size();
    m_colIndicesSize = m_settings.m_width * m_settings.m_height;
    m_colIndices = new int[m_colIndicesSize];
    init();
}

Controller::~Controller() {
    std::cout << "Freeing Controller memory\n";

    for (auto elem: m_drawers)
        delete elem.second;
    delete m_colIndices;
}

void Controller::init() {
    // create drawers and set start drawer
    if (std::find(m_settings.m_drawers.begin(), m_settings.m_drawers.end(), "AlienBlob") != m_settings.m_drawers.end()) {
        m_drawers.insert(std::make_pair("AlienBlob", new AlienBlobDrawer(m_settings.m_width, m_settings.m_height, m_settings.m_palSize, m_camera)));
    }
    if (std::find(m_settings.m_drawers.begin(), m_settings.m_drawers.end(), "Bzr") != m_settings.m_drawers.end()) {
        m_drawers.insert(std::make_pair("Bzr", new BzrDrawer(m_settings.m_width, m_settings.m_height, m_settings.m_palSize, m_camera)));
    }
    if (std::find(m_settings.m_drawers.begin(), m_settings.m_drawers.end(), "GrayScott") != m_settings.m_drawers.end()) {
        m_drawers.insert(std::make_pair("GrayScott", new GrayScottDrawer(m_settings.m_width, m_settings.m_height, m_settings.m_palSize)));
    }
    if (m_camera != NULL)
        m_drawers.insert(std::make_pair("Video", new VideoDrawer(m_settings.m_width, m_settings.m_height, m_settings.m_palSize, m_camera)));
    m_drawers.insert(std::make_pair("Off", new OffDrawer(m_settings.m_width, m_settings.m_height, m_settings.m_palSize)));
    if (m_drawers.find(m_settings.m_startDrawerName) != m_drawers.end())
        changeDrawer({m_settings.m_startDrawerName});
    else
        changeDrawer({"AlienBlob"});
}

void Controller::start(int interval) {
    m_stop = false;
    auto run = [=]() {
      std::cout << "Controller started on thread " << std::this_thread::get_id() << std::endl;
        while (!m_stop) {
            loop(interval);
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        m_stop = false;
        std::cout << "Controller done\n";
    };
    m_thread = std::thread(run);
    m_thread.detach();
}

void Controller::stop() {
    std::cout << "Stopping controller\n";
    m_stop = true;
    if (m_thread.joinable()) {
        m_thread.join();
    }
    delete m_matrix;
    std::cout << "Stopped controller\n";
}

void Controller::loop(int interval) {
    static unsigned long lastUpdate = 0;
    m_frameTimer.tick(interval, [=]() {
	//static int i = 0;
	//if (++i >= 200) {
	//  exit(0);
	//}
        m_fpsCounter.tick();

        // auto diff = millis() - lastUpdate;
        // if (diff > 30) {
        //     std::cout << diff << std::endl;
        // }
        // lastUpdate = millis();
    
        // change to Video drawer if faces have been detected or change
        // from video drawer is no faces detected
        if (m_faceDetect != NULL) {
            unsigned long faceTimeDiff = millis() - m_faceDetect->lastDetection();
            if (faceTimeDiff < m_settings.m_faceVideoDrawerTimeout && m_currDrawer->name().compare("Off") != 0 && m_currDrawer->name().compare("Video") != 0) {
                //std::cout << "faceTimeDiff=" << faceTimeDiff << "; faceVideoDrawerTimeout=" << m_settings.m_faceVideoDrawerTimeout << std::endl;
                changeDrawer({"Video"});
            } else if (faceTimeDiff > m_settings.m_faceVideoDrawerTimeout && m_currDrawer->name().compare("Video") == 0) {
                //std::cout << "faceTimeDiff=" << faceTimeDiff << "; faceVideoDrawerTimeout=" << m_settings.m_faceVideoDrawerTimeout << std::endl;
                changeDrawer({"GrayScott", "Bzr", "AlienBlob"});
            }

        // Change drawer every so often, but only to video if faces were detected
        if (m_drawerChangeTimer.tick(NULL)) {
            if (m_currDrawer->name().compare("Video") == 0)
                randomizeSettings(m_currDrawer);
            else
                changeDrawer(m_settings.m_drawers);
        }
        } else if (m_camera != NULL) {
            if (m_drawerChangeTimer.tick(NULL)) {
                auto drawers = m_settings.m_drawers;
                drawers.push_back("Video");
                changeDrawer(drawers);
            }
        } else {
            if (m_drawerChangeTimer.tick(NULL)) {
                changeDrawer(m_settings.m_drawers);
            }
        }

	// block until current frame is ready
	if (m_drawFuture.valid()) {
	  m_drawFuture.get();
	}

        // update output matrix
        for (int y = 0; y < m_settings.m_height; y++) {
            for (int x = 0; x < m_settings.m_width; x++) {
                Color24 col = m_palettes.get(m_currPalIndex, m_colIndices[x + y * m_settings.m_width]);
                m_matrix->setPixel(x, y, col.r, col.g, col.b);
            }
        }

        // start draw() in background
	m_drawFuture = std::async(std::launch::async, [this](){
	    while (m_currDrawer->isPaused()) {
	      std::this_thread::sleep_for(std::chrono::milliseconds(1));
	    }
	    m_currDrawer->draw(m_colIndices);
	  });
        m_matrix->update();
    });
}


const std::map<std::string,int>& Controller::settings() const {
    return m_currDrawer->settings();
}

const std::map<std::string,std::pair<int,int>>& Controller::settingsRanges() const {
    return m_currDrawer->settingsRanges();
}

void Controller::setSettings(const std::map<std::string,int>& settings) {
    m_currDrawer->setSettings(settings);
    m_drawerChangeTimer.reset();
}

std::string Controller::currDrawerName() const {
    return m_currDrawer->name();
}

std::vector<std::string> Controller::drawerNames() const {
    std::vector<std::string> names;
    for (auto& d: m_drawers)
        names.push_back(d.first);
    return names;
}

void Controller::changeDrawer(const std::vector<std::string>& names) {
    std::string name;
    assert(names.size() > 0);
    if (names.size() == 1)
        name = names[0];
    else
        name = names[random2() % names.size()];

    if (m_drawers.find(name) == m_drawers.end()) {
        std::cout << "Invalid drawer name: " << name << std::endl;
        return;
    }

    std::cout << "Changing to drawer: " << name << std::endl;
    Drawer* nextDrawer = m_drawers[name];
    randomizeSettings(nextDrawer);
    if (m_currDrawer) {
        m_currDrawer->cleanup();
    }
    m_currDrawer = nextDrawer;

    m_drawerChangeTimer.reset();
}

void Controller::randomizeSettings(Drawer* drawer) {
    drawer->setPaused(true);
    m_currPalIndex = 380; //random2() % m_palettes.size();
    drawer->randomizeSettings();

    std::cout << "New palette=" << m_currPalIndex;
    for (auto& s: drawer->settings()) {
        std::cout << " " << s.first << "=" << s.second;
    }
    std::cout << std::endl;

    m_drawerChangeTimer.reset();
    drawer->setPaused(false);
    std::cout << "Randomized settings for drawer: " << drawer->name() << "\n";
}
