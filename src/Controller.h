#ifndef CONTROLLER_H
#define CONTROLLER_H

#include "Drawer.h"
#include "Palette.h"
#include "Util.h"
#include "Camera.h"
#include "Matrix.h"
#include "FaceDetect.h"

#include <map>
#include <vector>
#include <iostream>
#include <thread>
#include <string>

typedef enum {
    HZELLER_RPI_MATRIX,
    SERIAL_MATRIX,
    COMPUTER_SCREEN_MATRIX
} MatrixType;

struct ControllerSettings {
    ControllerSettings(const std::string& configFilename);

    MatrixType m_matrixType;
    int m_fps;
    int m_width, m_height;
    int m_palSize;
    std::string m_device;
    bool m_layoutLeftToRight;
    std::string m_startDrawerName;
    std::vector<std::string> m_drawers;
    int m_drawerChangeInterval;
    int m_screenShowMultiplier;
    int m_baseColorsPerPalette;
    int m_faceVideoDrawerTimeout;
    int m_faceDetectFps;
    CameraSettings m_cameraSettings;
};

class Controller {
public:
    Controller(Matrix* matrix, const ControllerSettings& settings, const std::vector<int>& baseColors, Camera* camera, FaceDetect* faceDetect);

    ~Controller();

    const unsigned char* rawData(size_t& size);

    void start(int interval);
    void stop();
    void loop(int interval);

private:    
    const std::map<std::string,int>& settings();
    const std::map<std::string,std::pair<int,int> >& settingsRanges();
    void setSettings(const std::map<std::string,int>& settings);
    std::string currDrawerName();
    std::vector<std::string> drawerNames();
    void randomizeSettings(Drawer* drawer);
    void changeDrawer(std::vector<std::string> names);
    void init();

    Matrix* m_matrix;
    ControllerSettings m_settings;
    
    Palettes m_palettes;
    int m_currPalIndex; // index of current palette
    Serial m_serial;

    Camera* m_camera;
    FaceDetect* m_faceDetect;

    std::map<std::string,Drawer*> m_drawers;
    Drawer* m_currDrawer;
    IntervalTimer m_drawerChangeTimer;

    int* m_colIndices; // stores current color indices before mapping to rgb
    int m_colIndicesSize; // size of color indices array

    FpsCounter m_fpsCounter;
    FrameTimer m_frameTimer;
    bool m_stop;
    std::thread m_thread;
};

#endif
