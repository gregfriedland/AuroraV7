cmake_minimum_required (VERSION 2.8.9)
project (AuroraV6)

file(GLOB SRCS src/*.cpp)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")

find_package(OpenCV REQUIRED)
add_executable(${PROJECT_NAME} ${SRCS})

# add_subdirectory(json)
target_include_directories(${PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/json/src)
if(APPLE)
  add_definitions(-DMACOSX)
  target_link_libraries(${PROJECT_NAME} ${OpenCV_LIBS})
elseif(UNIX)
  add_definitions(-DLINUX)
  target_link_libraries(${PROJECT_NAME} ${OpenCV_LIBS} -lraspicam -lmmal -lmmal_core -lmmal_util -L/opt/vc/lib)
  add_subdirectory(raspicam)
endif()


file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/haarcascade_frontalface_alt2.xml
    DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
add_definitions(-DFACE_CASCADE_FILE="haarcascade_frontalface_alt2.xml")

add_executable(detect_faces_test detect_faces_test.cpp)
target_link_libraries(detect_faces_test ${OpenCV_LIBS})
