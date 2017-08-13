cmake_minimum_required (VERSION 3.0)
project(AuroraV6)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")

set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CMAKE_SOURCE_DIR}/cmake/")

find_package(OpenCV REQUIRED)
find_package(Protobuf REQUIRED)
find_package(GRPC REQUIRED)

file(GLOB PROTOS "${CMAKE_CURRENT_SOURCE_DIR}/protos/*.proto")
PROTOBUF_GENERATE_CPP(PROTO_SRCS PROTO_HDRS ${PROTOS})
PROTOBUF_GENERATE_GRPC_CPP(GRPC_SRCS GRPC_HDRS ${PROTOS})

SET(SRCS_MATRIX
  ${CMAKE_CURRENT_SOURCE_DIR}/src/AuroraMatrix.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Palette.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Serial.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Util.cpp
)

SET(SRCS_PATTERN_GEN
  ${CMAKE_CURRENT_SOURCE_DIR}/src/AlienBlob.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/AuroraPatternGen.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Bzr.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Camera.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Controller.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/FaceDetect.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/GinzburgLandau.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/GrayScott.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Off.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Palette.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/ReactionDiffusion.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Serial.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Util.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Video.cpp
)

if(${CMAKE_SYSTEM_PROCESSOR} MATCHES "arm") 
  add_subdirectory(raspicam)

  file(GLOB RPI_RGB_MATRIX_SRCS
    ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.c
  )

  add_executable(AuroraV6-matrix
    ${SRCS_MATRIX}
    ${RPI_RGB_MATRIX_SRCS}
    ${PROTO_SRCS}
    ${PROTO_HDRS}
    ${GRPC_SRCS}
    ${GRPC_HDRS}
  )
  target_link_libraries(AuroraV6-matrix
      ${OpenCV_LIBS}
      ${CMAKE_CURRENT_BINARY_DIR}/raspicam/src/libraspicam_cv.so
      ${PROTOBUF_LIBRARIES}
      ${GRPC_LIBRARIES}
  )
  target_include_directories(AuroraV6-matrix PRIVATE
      ${CMAKE_CURRENT_BINARY_DIR}
      ${CMAKE_CURRENT_SOURCE_DIR}/json/src
      ${CMAKE_CURRENT_SOURCE_DIR}/raspicam/src
      ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/include
  )
  add_executable(AuroraV6-patterngen
      ${SRCS_PATTERN_GEN}
      ${RPI_RGB_MATRIX_SRCS}
      ${PROTO_SRCS}
      ${PROTO_HDRS}
      ${GRPC_SRCS}
      ${GRPC_HDRS}
  )
  target_link_libraries(AuroraV6-patterngen
      ${OpenCV_LIBS}
      ${CMAKE_CURRENT_BINARY_DIR}/raspicam/src/libraspicam_cv.so
      ${PROTOBUF_LIBRARIES}
      ${GRPC_LIBRARIES}
  )
  target_include_directories(AuroraV6-patterngen PRIVATE
      ${CMAKE_CURRENT_BINARY_DIR}
      ${CMAKE_CURRENT_SOURCE_DIR}/json/src
      ${CMAKE_CURRENT_SOURCE_DIR}/raspicam/src
      ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/include
  )
  target_compile_options(AuroraV6-patterngen PUBLIC -mfpu=neon -mfloat-abi=hard -mtune=cortex-a53)
else()
  add_executable(AuroraV6-matrix ${SRCS_MATRIX} ${PROTO_SRCS} ${PROTO_HDRS} ${GRPC_SRCS} ${GRPC_HDRS})
  target_link_libraries(AuroraV6-matrix
      ${OpenCV_LIBS}
      ${PROTOBUF_LIBRARIES}
      ${GRPC_LIBRARIES}
  )
  target_include_directories(AuroraV6-matrix PRIVATE
      ${CMAKE_CURRENT_BINARY_DIR}
      ${CMAKE_CURRENT_SOURCE_DIR}/json/src
  )

  add_executable(AuroraV6-patterngen ${SRCS_PATTERN_GEN} ${PROTO_SRCS} ${PROTO_HDRS} ${GRPC_SRCS} ${GRPC_HDRS})
  target_link_libraries(AuroraV6-patterngen
      ${OpenCV_LIBS}
      ${PROTOBUF_LIBRARIES}
      ${GRPC_LIBRARIES}
  )
  target_include_directories(AuroraV6-patterngen PRIVATE
      ${CMAKE_CURRENT_BINARY_DIR}
      ${CMAKE_CURRENT_SOURCE_DIR}/json/src
  )
endif()


file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/haarcascade_frontalface_alt2.xml
    DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
add_definitions(-DFACE_CASCADE_FILE="${CMAKE_CURRENT_BINARY_DIR}/haarcascade_frontalface_alt2.xml")

add_executable(detect_faces_test src/detect_faces_test.cpp)
target_link_libraries(detect_faces_test ${OpenCV_LIBS})
