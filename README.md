# AuroraV6
Software for generative patterns on LED matrices; now with a pure C++ core

## Requirements
* libuv: install into /usr/local
* opencv2: install into /usr/local
** Build with: `cmake -D CMAKE_BUILD_TYPE=RELEASE -D CMAKE_INSTALL_PREFIX=/usr/local -DWITH_QT=OFF -DWITH_GTK=OFF -DWITH_FFMPEG=OFF ..`

## Dependencies
* [libuv-webserver](https://github.com/springmeyer/libuv-webserver) is used as the webserver
* [lodepng](https://github.com/lvandeve/lodepng) is used to create pngs
* gcc 4.8 is need for c++11 features (see Raspi install instructions [here](http://raspberrypi.stackexchange.com/a/27968))