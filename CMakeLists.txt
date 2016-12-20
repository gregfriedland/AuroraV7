cmake_minimum_required (VERSION 3.0)
project(AuroraV6)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")

find_package(OpenCV REQUIRED)

if(APPLE)
  file(GLOB SRCS
         ${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp
  )
  add_executable(${PROJECT_NAME} ${SRCS})

  add_definitions(-DMACOSX)
  target_link_libraries(${PROJECT_NAME} ${OpenCV_LIBS})
  target_include_directories(${PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/json/src)
elseif(UNIX)
  file(GLOB SRCS
         ${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp
         ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.cc
         ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.cc
         ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/lib/*.c
  )
  add_executable(${PROJECT_NAME} ${SRCS})

  add_definitions(-DLINUX)
  add_subdirectory(raspicam)
  target_link_libraries(${PROJECT_NAME} ${OpenCV_LIBS} ${CMAKE_CURRENT_BINARY_DIR}/raspicam/src/libraspicam_cv.so)
  target_include_directories(${PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/json/src ${CMAKE_CURRENT_SOURCE_DIR}/raspicam/src ${CMAKE_CURRENT_SOURCE_DIR}/rpi-rgb-led-matrix/include)
endif()


file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/haarcascade_frontalface_alt2.xml
    DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
add_definitions(-DFACE_CASCADE_FILE="${CMAKE_CURRENT_BINARY_DIR}/haarcascade_frontalface_alt2.xml")

add_executable(detect_faces_test detect_faces_test.cpp)
target_link_libraries(detect_faces_test ${OpenCV_LIBS})
