// Vast majority of this code is from
// http://www.pjrc.com/teensy/benchmark_usb_serial_receive.html#code with license below.

/*  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, version 3 of the License.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <iostream>

#include "Serial.h"

 // function prototypes
static PORTTYPE open_port_and_set_baud_or_die(const char *name, long baud);
static int transmit_bytes(PORTTYPE port, const unsigned char *data, int len);
static void close_port(PORTTYPE port);
static void die(const char *format, ...) __attribute__ ((format (printf, 1, 2)));


Serial::Serial(string device) : m_device(device) {}

void Serial::connect() {
    m_port = open_port_and_set_baud_or_die(m_device.c_str(), BAUD);        
}

void Serial::close() {
    close_port(m_port);
}

void Serial::write(const unsigned char* buffer, int size) {
    errno = 0;
    int written = 0;
    do {
        int result = transmit_bytes(m_port, buffer, size);
        // cout << "Serial writing: " << size << " bytes; wrote: " << result << " bytes\n";
        if (errno != 0 || result == -1) {
            cout << "Serial error while writing: " << errno << endl;
            exit(1);
        }
        written += result;
    } while (written < size);
}

int Serial::read(int size, unsigned char* buffer) {
   return ::read(m_port, buffer, size);
}


PORTTYPE open_port_and_set_baud_or_die(const char *name, long baud)
{
    PORTTYPE fd;
#if defined(MACOSX)
    struct termios tinfo;
    fd = open(name, O_RDWR | O_NONBLOCK);
    if (fd < 0) die("unable to open port %s\n", name);
    if (tcgetattr(fd, &tinfo) < 0) die("unable to get serial parms\n");
    cfmakeraw(&tinfo);
    if (cfsetspeed(&tinfo, baud) < 0) die("error in cfsetspeed\n");
    tinfo.c_cflag |= CLOCAL;
    if (tcsetattr(fd, TCSANOW, &tinfo) < 0) die("unable to set baud rate\n");
    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) & ~O_NONBLOCK);
#elif defined(LINUX)
    struct termios tinfo;
    memset (&tinfo, 0, sizeof tinfo);
    struct serial_struct kernel_serial_settings;
    int r;
    fd = open(name, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) die("unable to open port %s\n", name);
    if (tcgetattr(fd, &tinfo) < 0) die("unable to get serial parms\n");

    tinfo.c_cflag     &=  ~PARENB;            // Make 8n1
    tinfo.c_cflag     &=  ~CSTOPB;
    tinfo.c_cflag     &=  ~CSIZE;
    tinfo.c_cflag     |=  CS8;

    tinfo.c_cflag     &=  ~CRTSCTS;           // no flow control
    tinfo.c_cc[VMIN]   =  1;                  // read doesn't block
    tinfo.c_cc[VTIME]  =  5;                  // 0.5 seconds read timeout
    tinfo.c_cflag     |=  CREAD | CLOCAL;     // turn on READ & ignore ctrl lines

    cfmakeraw(&tinfo);

    tcflush( fd, TCIFLUSH );

    if (cfsetspeed(&tinfo, baud) < 0) die("error in cfsetspeed\n");
    if (tcsetattr(fd, TCSANOW, &tinfo) < 0) die("unable to set baud rate\n");
    /* r = ioctl(fd, TIOCGSERIAL, &kernel_serial_settings); */
    /* if (r >= 0) { */
    /*     kernel_serial_settings.flags |= ASYNC_LOW_LATENCY; */
    /*     r = ioctl(fd, TIOCSSERIAL, &kernel_serial_settings); */
    /*     if (r >= 0) printf("set linux low latency mode\n"); */
    /* } */
#elif defined(WINDOWS)
    COMMCONFIG cfg;
    COMMTIMEOUTS timeout;
    DWORD n;
    char portname[256];
    int num;
    if (sscanf(name, "COM%d", &num) == 1) {
        sprintf(portname, "\\\\.\\COM%d", num); // Microsoft KB115831
    } else {
        strncpy(portname, name, sizeof(portname)-1);
        portname[n-1] = 0;
    }
    fd = CreateFile(portname, GENERIC_READ | GENERIC_WRITE,
        0, 0, OPEN_EXISTING, 0, NULL);
    if (fd == INVALID_HANDLE_VALUE) die("unable to open port %s\n", name);
    GetCommConfig(fd, &cfg, &n);
    //cfg.dcb.BaudRate = baud;
    cfg.dcb.BaudRate = 115200;
    cfg.dcb.fBinary = TRUE;
    cfg.dcb.fParity = FALSE;
    cfg.dcb.fOutxCtsFlow = FALSE;
    cfg.dcb.fOutxDsrFlow = FALSE;
    cfg.dcb.fOutX = FALSE;
    cfg.dcb.fInX = FALSE;
    cfg.dcb.fErrorChar = FALSE;
    cfg.dcb.fNull = FALSE;
    cfg.dcb.fRtsControl = RTS_CONTROL_ENABLE;
    cfg.dcb.fAbortOnError = FALSE;
    cfg.dcb.ByteSize = 8;
    cfg.dcb.Parity = NOPARITY;
    cfg.dcb.StopBits = ONESTOPBIT;
    cfg.dcb.fDtrControl = DTR_CONTROL_ENABLE;
    SetCommConfig(fd, &cfg, n);
    GetCommTimeouts(fd, &timeout);
    timeout.ReadIntervalTimeout = 0;
    timeout.ReadTotalTimeoutMultiplier = 0;
    timeout.ReadTotalTimeoutConstant = 1000;
    timeout.WriteTotalTimeoutConstant = 0;
    timeout.WriteTotalTimeoutMultiplier = 0;
    SetCommTimeouts(fd, &timeout);
#endif
    return fd;

}


int transmit_bytes(PORTTYPE port, const unsigned char *data, int len) {
#if defined(MACOSX) || defined(LINUX)
    return write(port, data, len);
#elif defined(WINDOWS)
    DWORD n;
    BOOL r;
    r = WriteFile(port, data, len, &n, NULL);
    if (!r) return 0;
    return n;
#endif
}


void close_port(PORTTYPE port) {
#if defined(MACOSX) || defined(LINUX)
    close(port);
#elif defined(WINDOWS)
    CloseHandle(port);
#endif
}



void die(const char *format, ...) {
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    exit(1);
}

