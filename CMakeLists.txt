cmake_minimum_required (VERSION 3.0)
project(AuroraV6)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11 -pg")
#-mcpu=cortex-a53 -march=armv8-a+crc -mtune=cortex-a53 -mfpu=neon-fp-armv8 -mfloat-abi=hard -mvectorize-with-neon-quad -mhard-float -funsafe-math-optimizations")

find_package(OpenCV REQUIRED)

if(${CMAKE_SYSTEM_PROCESSOR} MATCHES "arm") 
  add_subdirectory(raspicam)

  file(GLOB SRCS
         ${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp
         ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.cc
         ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.cc
         ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.c
  )
  add_executable(${PROJECT_NAME} ${SRCS})
  target_link_libraries(${PROJECT_NAME} ${OpenCV_LIBS} ${CMAKE_CURRENT_BINARY_DIR}/raspicam/src/libraspicam_cv.so)
  target_include_directories(${PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/json/src ${CMAKE_CURRENT_SOURCE_DIR}/raspicam/src ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/include)

  add_executable(neon_test neon_test.cpp)
  target_compile_options(neon_test PUBLIC -mfp16-format=alternative -mfp16-format -mfpu=neon-fp16)
else()
  file(GLOB SRCS
         ${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp
  )
  add_executable(${PROJECT_NAME} ${SRCS})

  target_link_libraries(${PROJECT_NAME} ${OpenCV_LIBS})
  target_include_directories(${PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/json/src)
endif()


file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/haarcascade_frontalface_alt2.xml
    DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
add_definitions(-DFACE_CASCADE_FILE="${CMAKE_CURRENT_BINARY_DIR}/haarcascade_frontalface_alt2.xml")

add_executable(detect_faces_test detect_faces_test.cpp)
target_link_libraries(detect_faces_test ${OpenCV_LIBS})
