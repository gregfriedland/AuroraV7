cmake_minimum_required (VERSION 3.0)
project(AuroraV6)

if (APPLE)
	add_definitions(-DMACOSX)
elseif (UNIX)
	add_definitions(-DLINUX)
	add_subdirectory(modules/raspicam)
elseif (WIN32)
	add_definitions(-DWINDOWS)
endif()

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -std=c++11 -O3 -g -fPIC")

file(GLOB SRCS
	${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp
	${CMAKE_CURRENT_SOURCE_DIR}/modules/rpi-rgb-led-matrix/lib/*.cc
	${CMAKE_CURRENT_SOURCE_DIR}/modules/rpi-rgb-led-matrix/lib/*.cc
	${CMAKE_CURRENT_SOURCE_DIR}/modules/rpi-rgb-led-matrix/lib/*.c
	${CMAKE_CURRENT_SOURCE_DIR}/modules/lodepng/lodepng.cpp
)
list(REMOVE_ITEM SRCS ${CMAKE_CURRENT_SOURCE_DIR}/src/WebServer.cpp)

add_executable(${PROJECT_NAME} ${SRCS})

target_include_directories(${PROJECT_NAME} PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/modules/libuv/include
	${CMAKE_CURRENT_SOURCE_DIR}/modules/rpi-rgb-led-matrix/include
	${CMAKE_CURRENT_SOURCE_DIR}/modules/lodepng
	${CMAKE_CURRENT_SOURCE_DIR}/modules/raspicam/src
)

target_link_libraries(${PROJECT_NAME} uv pthread m opencv_core opencv_objdetect raspicam)
