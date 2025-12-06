#!/bin/bash
#
# Install dependencies for AuroraV7
#
# Usage: sudo ./install-deps.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root (use sudo)"
   exit 1
fi

log_info "Installing AuroraV7 dependencies..."

# Update package list
apt-get update

# Install build tools and core dependencies
log_info "Installing build tools and core dependencies..."
apt-get install -y \
    cmake \
    build-essential \
    pkg-config \
    git \
    curl

# Install OpenCV
log_info "Installing OpenCV..."
apt-get install -y libopencv-dev

# Install gRPC and Protocol Buffers
log_info "Installing gRPC and Protocol Buffers..."
apt-get install -y \
    libgrpc-dev \
    libgrpc++-dev \
    libprotobuf-dev \
    protobuf-compiler \
    protobuf-compiler-grpc

# Install GStreamer (for libcamera support on Pi 5)
log_info "Installing GStreamer..."
apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

# Try to install libcamera packages (may not be available on all systems)
log_info "Installing libcamera (if available)..."
apt-get install -y gstreamer1.0-libcamera 2>/dev/null || true

log_info "Dependencies installed successfully!"
log_info ""
log_info "Next steps:"
log_info "  1. Initialize submodules: git submodule update --init --recursive"
log_info "  2. Build rpi-rgb-led-matrix: cd external/rpi-rgb-led-matrix && make -j4"
log_info "  3. Build AuroraV7: mkdir build && cd build && cmake .. && make -j4"
