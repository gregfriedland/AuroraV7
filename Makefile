
all: ./build ./aurora

./deps/http-parser:
	git clone --depth 1 git://github.com/joyent/http-parser.git ./deps/http-parser

./deps/libuv:
	git clone --depth 1 git://github.com/libuv/libuv.git ./deps/libuv

./deps/lodepng:
	git clone --depth 1 git://github.com/lvandeve/lodepng.git ./deps/lodepng

./deps/gyp:
	git clone --depth 1 https://chromium.googlesource.com/external/gyp.git ./deps/gyp

./build: ./deps/gyp ./deps/libuv ./deps/http-parser ./deps/lodepng
	deps/gyp/gyp --depth=. -Goutput_dir=./out -Icommon.gypi --generator-output=./build -Dlibrary=static_library -Duv_library=static_library -f make -Dclang=1


SOURCES=src/*.cpp deps/lodepng/lodepng.cpp
HEADERS=src/*.h

./aurora: $(SOURCES) $(HEADERS)
	make -C ./build/ aurora
	cp ./build/out/Release/aurora ./aurora

distclean:
	make clean
	rm -rf ./build

#test:
	#./build/out/Release/webserver & ./build/out/Release/webclient && killall webserver
	#./build/out/Release/webserver & wrk -d10 -t24 -c24 --latency http://127.0.0.1:8000

clean:
	rm -rf ./build/out/Release/obj.target/aurora/
	rm -f ./build/out/Release/aurora
	rm -f ./aurora

.PHONY: test
