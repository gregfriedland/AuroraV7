#ifndef CONTROLLER_H
#define CONTROLLER_H

#include "Drawer.h"
#include "Palette.h"
#include "Serial.h"
#include "Util.h"
#include "Camera.h"

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
        bool layoutLeftToRight, string startDrawerName, int fps, 
        int drawerChangeInterval, Camera* camera)
    : m_width(width), m_height(height), m_palSize(palSize), m_device(device),
      m_layoutLeftToRight(layoutLeftToRight),
      m_startDrawerName(startDrawerName), m_fps(fps),
      m_palettes(palSize, baseColors, numBaseColors, baseColorsPerPalette),
      m_serial(device), m_camera(camera), m_currDrawer(NULL), 
      m_drawerChangeTimer(drawerChangeInterval),
      m_fpsCounter(5000, "Controller")
    {
        m_currPalIndex = random2() % m_palettes.size();

        m_colIndicesSize = width * height;
        m_colIndices = new int[m_colIndicesSize];
        m_serialWriteBufferSize = width * height * 3 + 1;
        m_serialWriteBuffer = new unsigned char[m_serialWriteBufferSize];
        init();
    }

    ~Controller() {
        cout << "Freeing Controller memory\n";

        for (auto elem: m_drawers)
            delete elem.second;
        delete m_colIndices;
        delete m_serialWriteBuffer;
    }

    const unsigned char* rawData(int& size) {
        size = m_serialWriteBufferSize;
        return m_serialWriteBuffer;
    }

    void start();
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
    int m_fps;
    
    Palettes m_palettes;
    int m_currPalIndex; // index of current palette
    Serial m_serial;
    Camera* m_camera;

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

inline static void timer_cb(uv_timer_t* handle) {
    ((Controller*)handle->data)->loop();
}

#endif
