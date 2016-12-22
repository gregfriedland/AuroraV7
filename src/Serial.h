#ifndef SERIAL_H
#define SERIAL_H

#if defined(__APPLE__) || defined(__linux__)
#include <termios.h>
#include <sys/select.h>
#define PORTTYPE int
#define BAUD B115200
#if defined(__linux__)
#include <sys/ioctl.h>
#include <linux/serial.h>
#endif
#elif defined(_WIN32)
#include <windows.h>
#define PORTTYPE HANDLE
#define BAUD 115200
#else
#error "You must define the operating system\n"
#endif

class Serial {
public:
    Serial(std::string device);

    void connect();

    void close();

    void write(const unsigned char* buffer, int size);

    int read(int size, unsigned char* buffer);

private:
    std::string m_device;
    PORTTYPE m_port;
};

#endif