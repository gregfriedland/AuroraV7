#ifndef HZELLER_RPI_MATRIX_H
#define HZELLER_RPI_MATRIX_H

#include "Matrix.h"
#include "led-matrix.h"
#include <iostream>
#include <thread>
#include <mutex>
#include <chrono>
#include "threaded-canvas-manipulator.h"

using namespace rgb_matrix;

#if 0
void thread_func(size_t width, size_t height, unsigned char* data) {
    RGBMatrix::Options options;
    rgb_matrix::RuntimeOptions runtime;

    options.hardware_mapping = "regular";
    options.rows = 32;
    options.chain_length = width / 32;
    options.parallel = height / 32;
    options.show_refresh_rate = true;
    auto canvas = rgb_matrix::CreateMatrixFromOptions(options, runtime);
    if (canvas == NULL) {
        std::cout << "Unable to create hzeller rpi matrix\n";
        exit(1);
    }

    std::chrono::milliseconds sleepMs{20};
    while (true) {
        for (size_t x = 0; x < width; ++x) {
            for (size_t y = 0; y < height; ++y) {
                size_t index = y * width * 3 + x * 3;
                canvas->SetPixel(x, y, data[index], data[index + 1], data[index + 2]);
            }
        }
        std::this_thread::sleep_for(sleepMs);
    }

    delete canvas;
}
#endif

class HzellerRpiMatrixThread : public ThreadedCanvasManipulator {
 public:
    HzellerRpiMatrixThread(Canvas *canvas, size_t width, size_t height, unsigned char* data)
    : ThreadedCanvasManipulator(canvas), m_width(width), m_height(height), m_data(data)
    {}
  
    virtual void Run() {
        std::chrono::milliseconds sleepMs{20};
        while (running()) {
            for (size_t x = 0; x < m_width; ++x) {
                for (size_t y = 0; y < m_height; ++y) {
                    size_t index = y * m_width * 3 + x * 3;
                    canvas()->SetPixel(x, y, m_data[index], m_data[index + 1], m_data[index + 2]);
                }
            }
            std::this_thread::sleep_for(sleepMs);
        }
    }
 
 private:
    size_t m_width, m_height;
    unsigned char* m_data;
};

class HzellerRpiMatrix : public Matrix {
 public:
    HzellerRpiMatrix(size_t width, size_t height) : Matrix(width, height) {
        rgb_matrix::RuntimeOptions runtime;
        runtime.gpio_slowdown = 2;

        RGBMatrix::Options options;
        options.hardware_mapping = "regular";
        options.rows = 32;
        options.chain_length = width / 32;
        options.parallel = height / 32;
        options.show_refresh_rate = true;

        m_matrix = rgb_matrix::CreateMatrixFromOptions(options, runtime);
        if (m_matrix == NULL) {
          std::cout << "Unable to create hzeller rpi matrix\n";
          exit(1);
        }
        
        m_data = new unsigned char[width * height * 3];
        m_thread = new HzellerRpiMatrixThread(m_matrix, width, height, m_data);
        m_thread->Start();
          //        std::thread t(&thread_func, width, height, m_data);
          //        t.detach();
    }

    virtual ~HzellerRpiMatrix() {
        m_thread->Stop();
        delete m_thread;
        delete m_matrix;
        delete [] m_data;
    }
  
    virtual void setPixel(size_t x, size_t y, unsigned char r, unsigned char g, unsigned char b) {
        m_data[y * m_width * 3 + x * 3] = r;
        m_data[y * m_width * 3 + x * 3 + 1] = g;
        m_data[y * m_width * 3 + x * 3 + 2] = b;
        // m_canvas->SetPixel(x, y, r, g, b);
    }
  
    virtual void update() {   
      m_offscreenCanvas = m_matrix->SwapOnVSync(m_offscreenCanvas);//, 5);
    }
  
 private:
    RGBMatrix* m_matrix;
    ThreadedCanvasManipulator* m_thread;
    FrameCanvas* m_offscreenCanvas;   
    unsigned char* m_data;
};

#endif
