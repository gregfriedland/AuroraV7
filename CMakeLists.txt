cmake_minimum_required (VERSION 3.0)
project(AuroraV6)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")
#-mcpu=cortex-a53 -march=armv8-a+crc -mtune=cortex-a53 -mfpu=neon-fp-armv8 -mfloat-abi=hard -mvectorize-with-neon-quad -mhard-float -funsafe-math-optimizations")

find_package(OpenCV REQUIRED)

SET(SRCS_MATRIX
  ${CMAKE_CURRENT_SOURCE_DIR}/src/AuroraMatrix.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Palette.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Serial.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/Util.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/src/md5.cpp  
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
  ${CMAKE_CURRENT_SOURCE_DIR}/src/md5.cpp  
)

if(${CMAKE_SYSTEM_PROCESSOR} MATCHES "arm") 
  add_subdirectory(raspicam)

  file(GLOB RPI_RGB_MATRIX_SRCS
    ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.c
  )

  add_executable(AuroraV6-matrix ${SRCS_MATRIX} ${RPI_RGB_MATRIX_SRCS})
  target_link_libraries(AuroraV6-matrix ${OpenCV_LIBS} ${CMAKE_CURRENT_BINARY_DIR}/raspicam/src/libraspicam_cv.so)
  target_include_directories(AuroraV6-matrix PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/json/src
      ${CMAKE_CURRENT_SOURCE_DIR}/raspicam/src
      ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/include
      ${CMAKE_CURRENT_SOURCE_DIR}/asio/asio/include)

  add_executable(AuroraV6-patterngen ${SRCS_PATTERN_GEN})
  target_link_libraries(AuroraV6-patterngen ${OpenCV_LIBS} ${CMAKE_CURRENT_BINARY_DIR}/raspicam/src/libraspicam_cv.so)
  target_include_directories(AuroraV6-patterngen PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/json/src
      ${CMAKE_CURRENT_SOURCE_DIR}/raspicam/src
      ${CMAKE_CURRENT_SOURCE_DIR}/asio/asio/include)
  target_compile_options(AuroraV6-patterngen PUBLIC -mfpu=neon -mfloat-abi=hard -mtune=cortex-a53)
else()
  add_executable(AuroraV6-matrix ${SRCS_MATRIX})
  target_link_libraries(AuroraV6-matrix ${OpenCV_LIBS})
  target_include_directories(AuroraV6-matrix PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/json/src
      ${CMAKE_CURRENT_SOURCE_DIR}/asio/asio/include)

  add_executable(AuroraV6-patterngen ${SRCS_PATTERN_GEN})
  target_link_libraries(AuroraV6-patterngen ${OpenCV_LIBS})
  target_include_directories(AuroraV6-patterngen PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/json/src
      ${CMAKE_CURRENT_SOURCE_DIR}/asio/asio/include)
endif()


file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/haarcascade_frontalface_alt2.xml
    DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
add_definitions(-DFACE_CASCADE_FILE="${CMAKE_CURRENT_BINARY_DIR}/haarcascade_frontalface_alt2.xml")

add_executable(detect_faces_test src/detect_faces_test.cpp)
target_link_libraries(detect_faces_test ${OpenCV_LIBS})
