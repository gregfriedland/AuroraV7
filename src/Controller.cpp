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

#define WINDOW_NAME "Aurora"


ControllerSettings::ControllerSettings(const std::string& configFilename) {
    try {
        std::ifstream ifs(configFilename);
        json j;
        ifs >> j;

        m_width = j["width"];
        m_height = j["height"];
        m_palSize = j["paletteSize"];
        m_fps = j["fps"];
        m_startDrawerName = j["startDrawer"];
        for (auto& d: j["drawers"]) {
            m_drawers.push_back(d);
        }
        m_drawerChangeInterval = j["drawerChangeInterval"];
        m_faceDetectFps = j["faceDetection"]["fps"];
        m_faceVideoDrawerTimeout = j["faceDetection"]["videoDrawerTimeout"];
        m_screenShowMultiplier = j["screenShowMultiplier"];
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

Controller::Controller(const ControllerSettings& settings, const std::vector<int>& baseColors,
    Camera* camera, FaceDetect* faceDetect)
: m_settings(settings), m_camera(camera), m_faceDetect(faceDetect),
  m_palettes(m_settings.m_palSize, baseColors, m_settings.m_baseColorsPerPalette),
  m_currDrawer(NULL), m_fpsCounter(30000, "Controller"), m_serial(m_settings.m_device),
  m_drawerChangeTimer(m_settings.m_drawerChangeInterval) {
    m_currPalIndex = random2() % m_palettes.size();

    m_colIndicesSize = m_settings.m_width * m_settings.m_height;
    m_colIndices = new int[m_colIndicesSize];
    m_serialWriteBufferSize = m_settings.m_width * m_settings.m_height * 3 + 1;
    m_serialWriteBuffer = new unsigned char[m_serialWriteBufferSize];
    init();
}

Controller::~Controller() {
    std::cout << "Freeing Controller memory\n";

    for (auto elem: m_drawers)
        delete elem.second;
    delete m_colIndices;
    delete m_serialWriteBuffer;
}

const unsigned char* Controller::rawData(int& size) {
    size = m_serialWriteBufferSize;
    return m_serialWriteBuffer;
}

void Controller::init()
{
    // create drawers and set start drawer
    m_drawers.insert(std::make_pair("AlienBlob", new AlienBlobDrawer(m_settings.m_width, m_settings.m_height, m_settings.m_palSize, m_camera)));
    m_drawers.insert(std::make_pair("Bzr", new BzrDrawer(m_settings.m_width, m_settings.m_height, m_settings.m_palSize, m_camera)));
    m_drawers.insert(std::make_pair("GrayScott", new GrayScottDrawer(m_settings.m_width, m_settings.m_height, m_settings.m_palSize, m_camera)));
    if (m_camera != NULL)
        m_drawers.insert(std::make_pair("Video", new VideoDrawer(m_settings.m_width, m_settings.m_height, m_settings.m_palSize, m_camera)));
    m_drawers.insert(std::make_pair("Off", new OffDrawer(m_settings.m_width, m_settings.m_height, m_settings.m_palSize)));
    if (m_drawers.find(m_settings.m_startDrawerName) != m_drawers.end())
        changeDrawer({m_settings.m_startDrawerName});
    else
        changeDrawer({"AlienBlob"});

    // create serial connection
    if (m_settings.m_device.size() > 0) {
        m_serial.connect();
    }

    if (m_settings.m_screenShowMultiplier) {
        cv::namedWindow(WINDOW_NAME, CV_WINDOW_AUTOSIZE);
        cv::moveWindow(WINDOW_NAME, 0, 0);
        std::cout << "Creating video window\n";
    }
}

void Controller::start(int interval) {
    std::cout << "Controller started\n";
    m_stop = false;
    auto run = [=]() {
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

    if (m_settings.m_device.size() > 0) {
        std::cout << "Closing serial port\n";
        m_serial.close();
    }
    std::cout << "Stopped controller\n";
}

void Controller::loop(int interval) {
    static unsigned long lastUpdate = 0;
    m_frameTimer.tick(interval, [=]() {
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

    // update drawer
    while (m_currDrawer->isPaused()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
        m_currDrawer->draw(m_colIndices);

        cv::Mat img;
        if (m_settings.m_screenShowMultiplier) {
            img = cv::Mat(m_settings.m_height * m_settings.m_screenShowMultiplier,
                m_settings.m_width * m_settings.m_screenShowMultiplier, CV_8UC3);
        }

        // pack data for serial transmission
        int i = 0;
        for (int y = 0; y < m_settings.m_height; y++) {
            for (int x = 0; x < m_settings.m_width; x++) {
                Color24 col = m_palettes.get(m_currPalIndex, m_colIndices[x + y * m_settings.m_width]);
                // if (x == 0 && y == 0)
                //  cout << "00 index=" << m_colIndices[x + y * m_width] << " rgb=" << (int)col.r << " " << (int)col.g << " " << (int)col.b << endl;
                m_serialWriteBuffer[i++] = std::min((unsigned char)254, col.r);
                m_serialWriteBuffer[i++] = std::min((unsigned char)254, col.g);
                m_serialWriteBuffer[i++] = std::min((unsigned char)254, col.b);

                if (m_settings.m_screenShowMultiplier) {
                    int m = m_settings.m_screenShowMultiplier;
                    for (int xx = 0; xx < m; ++xx) {
                        for (int yy = 0; yy < m; ++yy) {
                            cv::Vec3b& pix = img.at<cv::Vec3b>(y * m + yy, x * m + xx);
                            pix[0] = col.r;
                            pix[1] = col.g;
                            pix[2] = col.b;
                        }
                    }
                }
            }
        }
        m_serialWriteBuffer[i++] = 255;

        if (m_settings.m_screenShowMultiplier) {
            cv::imshow(WINDOW_NAME, img);
            cv::waitKey(1);            
        }

        // send serial data
        if (m_settings.m_device.size() > 0) {
            m_serial.write(m_serialWriteBuffer, m_serialWriteBufferSize);

            unsigned char buffer[256];
            if (m_serial.read(256, buffer) > 0)
                std::cout << "read: " << (unsigned int) buffer[0] << std::endl;
        }


    });
}


const std::map<std::string,int>& Controller::settings() {
    return m_currDrawer->settings();
}

const std::map<std::string,std::pair<int,int> >& Controller::settingsRanges() {
    return m_currDrawer->settingsRanges();
}

void Controller::setSettings(const std::map<std::string,int>& settings) {
    m_currDrawer->setSettings(settings);
    m_drawerChangeTimer.reset();
}

std::string Controller::currDrawerName() {
    return m_currDrawer->name();
}

std::vector<std::string> Controller::drawerNames() {
    std::vector<std::string> names;
    for (auto& d: m_drawers)
        names.push_back(d.first);
    return names;
}

void Controller::changeDrawer(std::vector<std::string> names) {
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
    m_currPalIndex = random2() % m_palettes.size();
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
