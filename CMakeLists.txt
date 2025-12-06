cmake_minimum_required(VERSION 3.16)
project(AuroraV7)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -Wall")

# Find packages
find_package(PkgConfig REQUIRED)
find_package(OpenCV REQUIRED)
find_package(Protobuf REQUIRED)

pkg_check_modules(GRPC REQUIRED grpc++)

# Check for GStreamer (needed for libcamera backend on Pi 5)
pkg_check_modules(GSTREAMER gstreamer-1.0)

#------------------------------------------------------------------------------
# Submodule paths
#------------------------------------------------------------------------------
set(NLOHMANN_JSON_DIR ${CMAKE_SOURCE_DIR}/external/nlohmann-json)
set(RGB_MATRIX_DIR ${CMAKE_SOURCE_DIR}/external/rpi-rgb-led-matrix)

# Include directories
include_directories(
    ${CMAKE_SOURCE_DIR}/src/cpp
    ${CMAKE_BINARY_DIR}
    ${OpenCV_INCLUDE_DIRS}
    ${GRPC_INCLUDE_DIRS}
    ${Protobuf_INCLUDE_DIRS}
    ${NLOHMANN_JSON_DIR}/include
    ${RGB_MATRIX_DIR}/include
    /usr/local/include
)

# Link directories
link_directories(
    ${RGB_MATRIX_DIR}/lib
    /usr/local/lib
    ${GRPC_LIBRARY_DIRS}
)

#------------------------------------------------------------------------------
# Generate protobuf files
#------------------------------------------------------------------------------
find_program(GRPC_CPP_PLUGIN grpc_cpp_plugin)
if(NOT GRPC_CPP_PLUGIN)
    message(FATAL_ERROR "grpc_cpp_plugin not found")
endif()

set(PROTO_DIR ${CMAKE_SOURCE_DIR}/src/protos)
set(PROTO_FILE ${PROTO_DIR}/Aurora.proto)

# Generate protobuf and grpc sources
add_custom_command(
    OUTPUT ${CMAKE_BINARY_DIR}/Aurora.pb.cc ${CMAKE_BINARY_DIR}/Aurora.pb.h
           ${CMAKE_BINARY_DIR}/Aurora.grpc.pb.cc ${CMAKE_BINARY_DIR}/Aurora.grpc.pb.h
    COMMAND ${Protobuf_PROTOC_EXECUTABLE}
        -I ${PROTO_DIR}
        --cpp_out=${CMAKE_BINARY_DIR}
        --grpc_out=${CMAKE_BINARY_DIR}
        --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN}
        ${PROTO_FILE}
    DEPENDS ${PROTO_FILE}
    COMMENT "Generating protobuf and gRPC sources"
)

set(PROTO_SRCS
    ${CMAKE_BINARY_DIR}/Aurora.pb.cc
    ${CMAKE_BINARY_DIR}/Aurora.grpc.pb.cc
)

#------------------------------------------------------------------------------
# Camera backend detection
# Priority: raspicam (Pi 4 and earlier) > libcamera (Pi 5) > OpenCV default
#------------------------------------------------------------------------------
find_library(RASPICAM_LIB raspicam)
find_library(RASPICAM_CV_LIB raspicam_cv)

set(CAMERA_LIBS "")
set(CAMERA_DEFINES "")

if(RASPICAM_LIB AND RASPICAM_CV_LIB)
    # Use raspicam for Pi 4 and earlier
    set(CAMERA_LIBS raspicam raspicam_cv)
    set(CAMERA_DEFINES USE_RASPICAM)
    message(STATUS "Camera backend: raspicam (legacy Pi camera)")
elseif(GSTREAMER_FOUND)
    # Use libcamera via GStreamer for Pi 5
    set(CAMERA_DEFINES USE_LIBCAMERA)
    message(STATUS "Camera backend: libcamera via GStreamer (Pi 5)")
else()
    # Fallback to standard OpenCV VideoCapture
    message(STATUS "Camera backend: OpenCV VideoCapture (default)")
endif()

#------------------------------------------------------------------------------
# Common source files (used by AuroraPatternGen)
#------------------------------------------------------------------------------
set(COMMON_SRCS
    src/cpp/Controller.cpp
    src/cpp/Palette.cpp
    src/cpp/Util.cpp
    src/cpp/Camera.cpp
    src/cpp/FaceDetect.cpp
    src/cpp/Video.cpp
    src/cpp/Serial.cpp
    src/cpp/AlienBlob.cpp
    src/cpp/Bzr.cpp
    src/cpp/GinzburgLandau.cpp
    src/cpp/GrayScott.cpp
    src/cpp/ReactionDiffusion.cpp
    src/cpp/Off.cpp
)

#------------------------------------------------------------------------------
# Check if building on ARM (Raspberry Pi)
#------------------------------------------------------------------------------
if(CMAKE_SYSTEM_PROCESSOR MATCHES "arm" OR CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64")
    set(IS_ARM TRUE)
    add_compile_definitions(__arm__)
    message(STATUS "Building for ARM architecture")
else()
    set(IS_ARM FALSE)
    message(STATUS "Building for non-ARM architecture (some features may be disabled)")
endif()

#------------------------------------------------------------------------------
# Build rpi-rgb-led-matrix from submodule (ARM only)
#------------------------------------------------------------------------------
if(IS_ARM AND EXISTS "${RGB_MATRIX_DIR}/Makefile")
    # Build the library from submodule if not already built
    if(NOT EXISTS "${RGB_MATRIX_DIR}/lib/librgbmatrix.a")
        message(STATUS "Building rpi-rgb-led-matrix from submodule...")
        execute_process(
            COMMAND make -j4
            WORKING_DIRECTORY ${RGB_MATRIX_DIR}
            RESULT_VARIABLE RGB_MATRIX_BUILD_RESULT
        )
        if(NOT RGB_MATRIX_BUILD_RESULT EQUAL 0)
            message(WARNING "Failed to build rpi-rgb-led-matrix")
        endif()
    endif()

    if(EXISTS "${RGB_MATRIX_DIR}/lib/librgbmatrix.a")
        set(RGB_MATRIX_LIB ${RGB_MATRIX_DIR}/lib/librgbmatrix.a)
        message(STATUS "Using rpi-rgb-led-matrix from submodule: ${RGB_MATRIX_LIB}")
        set(HAS_RGB_MATRIX TRUE)
    else()
        message(STATUS "rpi-rgb-led-matrix build failed")
        set(HAS_RGB_MATRIX FALSE)
    endif()
else()
    # Non-ARM or submodule not present - try system library
    find_library(RGB_MATRIX_LIB rgbmatrix)
    if(RGB_MATRIX_LIB)
        message(STATUS "Found rpi-rgb-led-matrix system library: ${RGB_MATRIX_LIB}")
        set(HAS_RGB_MATRIX TRUE)
    else()
        message(STATUS "rpi-rgb-led-matrix not found (not on ARM or submodule missing)")
        set(HAS_RGB_MATRIX FALSE)
    endif()
endif()

#------------------------------------------------------------------------------
# AuroraMatrix (server) - receives frames and displays on LED matrix
# Only built on ARM with rpi-rgb-led-matrix available
#------------------------------------------------------------------------------
if(HAS_RGB_MATRIX)
    add_executable(AuroraMatrix
        src/cpp/AuroraMatrix.cpp
        src/cpp/Serial.cpp
        src/cpp/Util.cpp
        ${PROTO_SRCS}
    )

    if(CAMERA_DEFINES)
        target_compile_definitions(AuroraMatrix PRIVATE ${CAMERA_DEFINES})
    endif()

    target_link_libraries(AuroraMatrix
        ${GRPC_LIBRARIES}
        ${Protobuf_LIBRARIES}
        ${OpenCV_LIBS}
        ${RGB_MATRIX_LIB}
        ${CAMERA_LIBS}
        pthread
    )
endif()

#------------------------------------------------------------------------------
# AuroraPatternGen (client) - generates patterns and sends to server
#------------------------------------------------------------------------------
add_executable(AuroraPatternGen
    src/cpp/AuroraPatternGen.cpp
    ${COMMON_SRCS}
    ${PROTO_SRCS}
)

if(CAMERA_DEFINES)
    target_compile_definitions(AuroraPatternGen PRIVATE ${CAMERA_DEFINES})
endif()

# Link libraries - rgbmatrix only if available
set(PATTERN_GEN_LIBS
    ${GRPC_LIBRARIES}
    ${Protobuf_LIBRARIES}
    ${OpenCV_LIBS}
    ${CAMERA_LIBS}
    pthread
)

if(HAS_RGB_MATRIX)
    list(APPEND PATTERN_GEN_LIBS ${RGB_MATRIX_LIB})
endif()

target_link_libraries(AuroraPatternGen ${PATTERN_GEN_LIBS})

#------------------------------------------------------------------------------
# Installation
#------------------------------------------------------------------------------
install(TARGETS AuroraPatternGen DESTINATION bin)
if(HAS_RGB_MATRIX)
    install(TARGETS AuroraMatrix DESTINATION bin)
endif()
