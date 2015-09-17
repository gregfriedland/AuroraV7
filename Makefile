all: ./build ./aurora

# only make raspicam c++ lib if we're on a raspi
UNAME_M := $(shell uname -m)
ifeq ($(UNAME_M),armv7l)
./deps/raspicam:
	git clone --depth 1 git://github.com/cedricve/raspicam ./deps/raspicam
	(cd ./deps/raspicam; mkdir -p build; cd build; cmake -DOpenCV_FOUND=0 ..; make)
DEPS=./deps/gyp ./deps/libuv ./deps/http-parser ./deps/lodepng ./deps/raspicam
CXXFLAGS=-DRASPI

install: ./deps/raspicam
	(cd ./deps/raspicam/build; make install; ldconfig)
else
DEPS=./deps/gyp ./deps/libuv ./deps/http-parser ./deps/lodepng
endif

./deps/http-parser:
	git clone --depth 1 git://github.com/joyent/http-parser.git ./deps/http-parser

./deps/libuv:
	git clone --depth 1 git://github.com/libuv/libuv.git ./deps/libuv

./deps/lodepng:
	git clone --depth 1 git://github.com/lvandeve/lodepng.git ./deps/lodepng

./deps/gyp:
	git clone --depth 1 https://chromium.googlesource.com/external/gyp.git ./deps/gyp

./build: $(DEPS)
	deps/gyp/gyp --depth=. -Goutput_dir=./out -Icommon.gypi --generator-output=./build -Dlibrary=static_library -Duv_library=static_library -f make -Dclang=1


SOURCES=src/*.cpp deps/lodepng/lodepng.cpp
HEADERS=src/*.h

./aurora: $(SOURCES) $(HEADERS)
	make -C ./build/ aurora
	cp ./build/out/Release/aurora ./aurora

distclean:
	make clean
	rm -rf ./build

clean:
	rm -rf ./build/out/Release/obj.target/aurora/
	rm -f ./build/out/Release/aurora
	rm -rf ./build/out/Debug/obj.target/aurora/
	rm -f ./build/out/Debug/aurora
	rm -f ./aurora

.PHONY: test
