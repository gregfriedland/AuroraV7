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
#include <uv.h>

using namespace std;

static void timer_cb(uv_timer_t* handle);

class Controller {
public:
    Controller(int width, int height, int palSize, string device, 
        int* baseColors, int numBaseColors, int baseColorsPerPalette,
        bool layoutLeftToRight, string startDrawerName,
        int drawerChangeInterval, Camera* camera, FaceDetect* faceDetect);

    ~Controller();

    const unsigned char* rawData(int& size);

    void start(int interval);
    void stop();

private:
    friend void timer_cb(uv_timer_t* handle);
    
    const map<string,int>& settings();
    const map< string,pair<int,int> >& settingsRanges();
    void setSettings(const map<string,int>& settings);
    string currDrawerName();
    vector<string> drawerNames();
    void randomizeSettings();

    void loop();
    void init();
    void changeDrawer(vector<string> names);

    int m_width, m_height, m_palSize;
    string m_device;
    bool m_layoutLeftToRight;
    string m_startDrawerName;
    
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
    uv_timer_t m_timer;
};

#endif
