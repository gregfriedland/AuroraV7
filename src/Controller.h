#ifndef CONTROLLER_H
#define CONTROLLER_H

#include "Drawer.h"
#include "Palette.h"
#include "Serial.h"
#include "Util.h"
#include "Camera.h"
#include "FaceDetect.h"

#include <map>
#include <vector>
#include <iostream>
#include <thread>
#include <string>

struct ControllerSettings {
    ControllerSettings(const std::string& configFilename);

    int m_fps;
    int m_width, m_height;
    int m_palSize;
    std::string m_device;
    bool m_layoutLeftToRight;
    std::string m_startDrawerName;
    int m_drawerChangeInterval;
    int m_screenShowMultiplier;
    int m_numBaseColors;
    int m_baseColorsPerPalette;
    int m_faceVideoDrawerTimeout;
    int m_cameraFps;
    int m_cameraWidth;
    int m_cameraHeight;
    int m_faceDetectFps;
};

class Controller {
public:
    Controller(const ControllerSettings& settings, int* baseColors, Camera* camera, FaceDetect* faceDetect);

    ~Controller();

    const unsigned char* rawData(int& size);

    void start(int interval);
    void stop();
    void loop(int interval);

private:    
    const map<string,int>& settings();
    const map< string,pair<int,int> >& settingsRanges();
    void setSettings(const map<string,int>& settings);
    string currDrawerName();
    vector<string> drawerNames();
    void randomizeSettings();

    void changeDrawer(vector<string> names);
    void init();

    ControllerSettings m_settings;
    
    Palettes m_palettes;
    int m_currPalIndex; // index of current palette
    Serial m_serial;

    Camera* m_camera;
    FaceDetect* m_faceDetect;

    map<string,Drawer*> m_drawers;
    Drawer* m_currDrawer;
    IntervalTimer m_drawerChangeTimer;

    int* m_colIndices; // stores current color indices before mapping to rgb
    int m_colIndicesSize; // size of color indices array
    unsigned char* m_serialWriteBuffer; // stores data in serial write order
    int m_serialWriteBufferSize;

    FpsCounter m_fpsCounter;
    FrameTimer m_frameTimer;
    bool m_stop;
    std::thread m_thread;
};

#endif
