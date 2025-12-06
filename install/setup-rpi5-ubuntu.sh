#!/bin/bash
#
# AuroraV7 Installation Script for Raspberry Pi 5 running Ubuntu
#
# Tested on: Ubuntu 22.04 LTS, Ubuntu 24.04 LTS
#
# This script installs all dependencies and builds the AuroraV7 LED matrix
# control software. It sets up:
#   - Build tools (cmake, g++)
#   - gRPC and Protocol Buffers
#   - OpenCV (for camera/face detection)
#   - hzeller's rpi-rgb-led-matrix library
#   - libcamera (Pi 5 camera support - replaces legacy raspicam)
#   - nlohmann/json header
#
# Usage: sudo ./setup-rpi5-ubuntu.sh [--no-start]
#
# Options:
#   --no-start    Don't start the service after installation
#

set -e

# Parse arguments
START_SERVICE=true
for arg in "$@"; do
    case $arg in
        --no-start)
            START_SERVICE=false
            shift
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root (use sudo)"
   exit 1
fi

# Check Ubuntu version
if [ -f /etc/os-release ]; then
    . /etc/os-release
    log_info "Detected OS: ${PRETTY_NAME}"
    if [[ "${ID}" != "ubuntu" ]]; then
        log_warn "This script is designed for Ubuntu. Other distros may work but are untested."
    fi
fi

# Get the actual user (not root)
ACTUAL_USER=${SUDO_USER:-$USER}
ACTUAL_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)

# Configuration
INSTALL_DIR="${ACTUAL_HOME}/src"
AURORA_DIR="${INSTALL_DIR}/AuroraV7"
RPI_RGB_LED_MATRIX_DIR="${INSTALL_DIR}/rpi-rgb-led-matrix"
RASPICAM_DIR="${INSTALL_DIR}/raspicam"
NUM_CORES=$(nproc)

log_info "Installing AuroraV7 for user: ${ACTUAL_USER}"
log_info "Install directory: ${INSTALL_DIR}"
log_info "Using ${NUM_CORES} cores for compilation"

# Create install directory
mkdir -p "${INSTALL_DIR}"
chown "${ACTUAL_USER}:${ACTUAL_USER}" "${INSTALL_DIR}"

#------------------------------------------------------------------------------
# Step 1: Update system and install base dependencies
#------------------------------------------------------------------------------
log_info "Step 1: Updating system and installing base dependencies..."

apt-get update
apt-get upgrade -y

apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
    autoconf \
    automake \
    libtool \
    curl \
    unzip

#------------------------------------------------------------------------------
# Step 2: Install gRPC and Protocol Buffers
#------------------------------------------------------------------------------
log_info "Step 2: Installing gRPC and Protocol Buffers..."

# Install from apt (Ubuntu 22.04+ has reasonably recent versions)
apt-get install -y \
    libgrpc-dev \
    libgrpc++-dev \
    libprotobuf-dev \
    protobuf-compiler \
    protobuf-compiler-grpc

# Verify installation
if ! command -v protoc &> /dev/null; then
    log_error "protoc not found after installation"
    exit 1
fi
log_info "protoc version: $(protoc --version)"

#------------------------------------------------------------------------------
# Step 3: Install OpenCV
#------------------------------------------------------------------------------
log_info "Step 3: Installing OpenCV..."

apt-get install -y \
    libopencv-dev \
    python3-opencv

# Verify installation
pkg-config --modversion opencv4 || pkg-config --modversion opencv

#------------------------------------------------------------------------------
# Step 4: Install nlohmann/json
#------------------------------------------------------------------------------
log_info "Step 4: Installing nlohmann/json..."

apt-get install -y nlohmann-json3-dev

#------------------------------------------------------------------------------
# Step 5: Install hzeller's rpi-rgb-led-matrix library
#------------------------------------------------------------------------------
log_info "Step 5: Installing rpi-rgb-led-matrix library..."

cd "${INSTALL_DIR}"

if [ -d "${RPI_RGB_LED_MATRIX_DIR}" ]; then
    log_warn "rpi-rgb-led-matrix directory exists, pulling latest..."
    cd "${RPI_RGB_LED_MATRIX_DIR}"
    sudo -u "${ACTUAL_USER}" git pull
else
    sudo -u "${ACTUAL_USER}" git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
    cd "${RPI_RGB_LED_MATRIX_DIR}"
fi

# Build the library
# Note: For Pi 5, we need to use the GPIO character device interface
log_info "Building rpi-rgb-led-matrix (this may take a while)..."
make clean || true
make -j${NUM_CORES}

# Install library and headers
make install-pkgconfig
ldconfig

#------------------------------------------------------------------------------
# Step 6: Install camera libraries
#------------------------------------------------------------------------------
log_info "Step 6: Installing camera libraries..."

# Pi 5 uses libcamera exclusively (legacy raspicam not supported)
# Install libcamera and GStreamer dependencies for camera support
apt-get install -y \
    libcamera-dev \
    libcamera-apps \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-libcamera \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    || true

# Try to install libcamera0 (version varies by Ubuntu release)
apt-get install -y libcamera0.3 || apt-get install -y libcamera0 || true

# For backwards compatibility, try to install raspicam if available
# This will work on Pi 4 and earlier, but may fail on Pi 5
cd "${INSTALL_DIR}"

# Check if we're on Pi 5 (BCM2712)
IS_PI5=false
if grep -q "BCM2712" /proc/cpuinfo 2>/dev/null; then
    IS_PI5=true
    log_warn "Raspberry Pi 5 detected - using libcamera (raspicam not supported)"
    log_warn "Camera features may require code updates to use libcamera API"
else
    # Try to install raspicam for older Pi models
    if [ -d "${RASPICAM_DIR}" ]; then
        log_warn "raspicam directory exists, pulling latest..."
        cd "${RASPICAM_DIR}"
        sudo -u "${ACTUAL_USER}" git pull || true
    else
        sudo -u "${ACTUAL_USER}" git clone https://github.com/cedricve/raspicam.git || true
    fi

    if [ -d "${RASPICAM_DIR}" ]; then
        cd "${RASPICAM_DIR}"
        mkdir -p build
        cd build
        cmake .. || log_warn "raspicam cmake failed - camera features may not work"
        make -j${NUM_CORES} || log_warn "raspicam build failed"
        make install || true
        ldconfig
    fi
fi

#------------------------------------------------------------------------------
# Step 7: Clone/update AuroraV7 repository
#------------------------------------------------------------------------------
log_info "Step 7: Setting up AuroraV7..."

cd "${INSTALL_DIR}"

if [ -d "${AURORA_DIR}" ]; then
    log_warn "AuroraV7 directory exists"
else
    log_info "Please clone AuroraV7 repository to ${AURORA_DIR}"
fi

#------------------------------------------------------------------------------
# Step 8: Build AuroraV7
#------------------------------------------------------------------------------
log_info "Step 8: Building AuroraV7..."

if [ ! -d "${AURORA_DIR}" ]; then
    log_error "AuroraV7 directory not found at ${AURORA_DIR}"
    log_error "Please clone the repository first"
    exit 1
fi

cd "${AURORA_DIR}"

# Create build directory
mkdir -p build
cd build

# Copy json.hpp if not present
if [ ! -f "${AURORA_DIR}/src/cpp/json.hpp" ]; then
    log_info "Downloading json.hpp..."
    curl -sL https://github.com/nlohmann/json/releases/download/v3.11.3/json.hpp \
        -o "${AURORA_DIR}/src/cpp/json.hpp"
fi

# Verify CMakeLists.txt exists (should be in repo)
if [ ! -f "${AURORA_DIR}/CMakeLists.txt" ]; then
    log_error "CMakeLists.txt not found in repository"
    exit 1
fi

# Build with CMake
cmake ..
make -j${NUM_CORES}

# Set ownership
chown -R "${ACTUAL_USER}:${ACTUAL_USER}" "${AURORA_DIR}"

#------------------------------------------------------------------------------
# Step 9: Setup systemd service
#------------------------------------------------------------------------------
log_info "Step 9: Setting up systemd service..."

# Update the service file with correct paths
SERVICE_FILE="/etc/systemd/system/aurorav7.service"

cat > "${SERVICE_FILE}" << SERVICEFILE
[Unit]
Description=AuroraV7 LED Matrix Driver
After=syslog.target network.target

[Service]
ExecStart=${AURORA_DIR}/build/AuroraMatrix ${AURORA_DIR}/config/machinations-matrix-192x96.json
Type=simple
PIDFile=/run/aurorav7.pid
WorkingDirectory=${AURORA_DIR}/build
Nice=-20
User=root
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEFILE

systemctl daemon-reload

# Enable service to start on boot
log_info "Enabling aurorav7 service..."
systemctl enable aurorav7

#------------------------------------------------------------------------------
# Step 10: Configure system for LED matrix
#------------------------------------------------------------------------------
log_info "Step 10: Configuring system for LED matrix..."

# Disable audio (conflicts with LED matrix GPIO)
if [ -f /boot/firmware/config.txt ]; then
    CONFIG_FILE="/boot/firmware/config.txt"
elif [ -f /boot/config.txt ]; then
    CONFIG_FILE="/boot/config.txt"
else
    log_warn "Could not find config.txt, skipping audio disable"
    CONFIG_FILE=""
fi

if [ -n "${CONFIG_FILE}" ]; then
    # Disable onboard audio
    if ! grep -q "^dtparam=audio=off" "${CONFIG_FILE}"; then
        echo "dtparam=audio=off" >> "${CONFIG_FILE}"
        log_info "Disabled onboard audio in ${CONFIG_FILE}"
    fi

    # For Pi 5, we may need additional GPIO configuration
    if ! grep -q "^gpio=0-27=a2" "${CONFIG_FILE}"; then
        # This may need adjustment based on your specific setup
        log_info "Note: Pi 5 may require additional GPIO configuration"
    fi
fi

# Increase GPU memory (helps with camera)
if [ -n "${CONFIG_FILE}" ]; then
    if ! grep -q "^gpu_mem=" "${CONFIG_FILE}"; then
        echo "gpu_mem=128" >> "${CONFIG_FILE}"
        log_info "Set GPU memory to 128MB"
    fi
fi

#------------------------------------------------------------------------------
# Step 11: Start service
#------------------------------------------------------------------------------
if [ "${START_SERVICE}" = true ]; then
    log_info "Step 11: Starting aurorav7 service..."

    # Check if reboot is needed first
    if [ -n "${CONFIG_FILE}" ]; then
        log_warn "System configuration was modified - service may not work until reboot"
    fi

    systemctl start aurorav7 || log_warn "Service failed to start - may need reboot first"

    # Show service status
    sleep 2
    systemctl status aurorav7 --no-pager || true
else
    log_info "Step 11: Skipping service start (--no-start specified)"
fi

#------------------------------------------------------------------------------
# Done!
#------------------------------------------------------------------------------
log_info "=============================================="
log_info "Installation complete!"
log_info "=============================================="
log_info ""
log_info "Built binaries are in: ${AURORA_DIR}/build/"
log_info "  - AuroraMatrix: LED matrix server (runs on Pi with LEDs)"
log_info "  - AuroraPatternGen: Pattern generator (can run remotely)"
log_info ""
log_info "Service status:"
log_info "  sudo systemctl status aurorav7"
log_info ""
log_info "View logs:"
log_info "  sudo journalctl -u aurorav7 -f"
log_info ""
log_info "To run manually:"
log_info "  sudo ${AURORA_DIR}/build/AuroraMatrix ${AURORA_DIR}/config/machinations-matrix-192x96.json"
log_info ""
if [ "${IS_PI5}" = true ]; then
    log_warn "Pi 5 detected: Camera features use libcamera API (code may need updates)"
fi
log_info "IMPORTANT: A reboot is recommended to apply GPIO/audio changes."
log_info "  sudo reboot"
