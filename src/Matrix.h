#ifndef MATRIX_H
#define MATRIX_H

class Matrix {
 public:
    Matrix(size_t width, size_t height)
    : m_width(width), m_height(height) {}

    virtual ~Matrix() {}
    virtual void setPixel(size_t x, size_t y, char r, char g, char b) = 0;
    virtual void update() = 0;

 protected:
    size_t m_width, m_height;
};

#endif
