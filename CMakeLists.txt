cmake_minimum_required (VERSION 2.8.9)
project (AuroraV6)

file(GLOB SRCS src/*.cpp)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")

find_package(OpenCV REQUIRED)
add_executable (aurora ${SRCS})

if(APPLE)
  add_definitions(-DMACOSX)
  target_link_libraries(aurora ${OpenCV_LIBS})
elseif(UNIX)
  add_definitions(-DLINUX)
  target_link_libraries(aurora ${OpenCV_LIBS} -lraspicam -lmmal -lmmal_core -lmmal_util -L/opt/vc/lib)
endif()


# add_executable(imshow_test src/imshow_test.cpp)
# target_link_libraries(imshow_test ${OpenCV_LIBS})
