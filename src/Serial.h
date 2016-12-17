#ifndef SERIAL_H
#define SERIAL_H

// One of these must be defined, usually via the Makefile
//#define MACOSX
//#define LINUX
//#define WINDOWS

#if defined(MACOSX) || defined(LINUX)
#include <termios.h>
#include <sys/select.h>
#define PORTTYPE int
#define BAUD B115200
#if defined(LINUX)
#include <sys/ioctl.h>
#include <linux/serial.h>
#endif
#elif defined(WINDOWS)
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