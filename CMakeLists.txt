cmake_minimum_required (VERSION 3.0)
project (AuroraV6)

file(GLOB SRCS src/*.cpp)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")

if(APPLE)
  add_definitions(-DMACOSX=1)
elseif(LINUX)
  add_definitions(-DLINUX=1)
endif()


find_package(OpenCV REQUIRED)
add_executable (aurora ${SRCS})
target_link_libraries(aurora ${OpenCV_LIBS})
