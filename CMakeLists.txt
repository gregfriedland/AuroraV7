cmake_minimum_required (VERSION 3.0)
project(AuroraV6)

file(GLOB SRCS src/*.cpp)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")

find_package(OpenCV REQUIRED)
add_executable(${PROJECT_NAME} ${SRCS})

if(APPLE)
  add_definitions(-DMACOSX)
  target_link_libraries(${PROJECT_NAME} ${OpenCV_LIBS})
  target_include_directories(${PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/json/src)
elseif(UNIX)
  add_definitions(-DLINUX)
  add_subdirectory(raspicam)
  add_subdirectory(rpi-rgb-led-matrix)
  target_link_libraries(${PROJECT_NAME} ${OpenCV_LIBS} ${CMAKE_CURRENT_BINARY_DIR}/raspicam/src/libraspicam_cv.so)
  target_include_directories(${PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/json/src ${CMAKE_CURRENT_SOURCE_DIR}/raspicam/src)
endif()


file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/haarcascade_frontalface_alt2.xml
    DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
add_definitions(-DFACE_CASCADE_FILE="${CMAKE_CURRENT_BINARY_DIR}/haarcascade_frontalface_alt2.xml")

add_executable(detect_faces_test detect_faces_test.cpp)
target_link_libraries(detect_faces_test ${OpenCV_LIBS})
