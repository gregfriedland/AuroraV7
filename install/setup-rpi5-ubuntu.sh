#!/bin/bash
#
# AuroraV7 Full Setup Script for Raspberry Pi 5 running Ubuntu
#
# This script:
#   1. Installs all dependencies
#   2. Builds AuroraV7
#   3. Sets up systemd service
#   4. Configures system for LED matrix
#
# Usage: sudo ./setup-rpi5-ubuntu.sh [OPTIONS]
#
# Options:
#   --no-start       Don't start the service after installation
#   --config FILE    Path to config file (default: config/machinations-matrix-192x96.json)
#

set -e

# Parse arguments
START_SERVICE=true
CONFIG_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-start)
            START_SERVICE=false
            shift
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
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

# Get the actual user (not root)
ACTUAL_USER=${SUDO_USER:-$USER}
ACTUAL_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)

# Find AuroraV7 directory (script should be run from repo or repo/install)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/../CMakeLists.txt" ]]; then
    AURORA_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
elif [[ -f "${SCRIPT_DIR}/CMakeLists.txt" ]]; then
    AURORA_DIR="${SCRIPT_DIR}"
else
    log_error "Cannot find AuroraV7 directory. Run this script from the repository."
    exit 1
fi

# Set default config file
if [[ -z "${CONFIG_FILE}" ]]; then
    CONFIG_FILE="${AURORA_DIR}/config/matrix-192x96.json"
fi

NUM_CORES=$(nproc)

log_info "AuroraV7 Setup Script"
log_info "====================="
log_info "User: ${ACTUAL_USER}"
log_info "AuroraV7 directory: ${AURORA_DIR}"
log_info "Config file: ${CONFIG_FILE}"
log_info "Using ${NUM_CORES} cores for compilation"

#------------------------------------------------------------------------------
# Step 1: Install dependencies
#------------------------------------------------------------------------------
log_info "Step 1: Installing dependencies..."

apt-get update

apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
    libopencv-dev \
    libgrpc-dev \
    libgrpc++-dev \
    libprotobuf-dev \
    protobuf-compiler \
    protobuf-compiler-grpc \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

# Try to install libcamera packages (Pi 5)
apt-get install -y gstreamer1.0-libcamera 2>/dev/null || true

#------------------------------------------------------------------------------
# Step 2: Initialize submodules
#------------------------------------------------------------------------------
log_info "Step 2: Initializing submodules..."

cd "${AURORA_DIR}"
sudo -u "${ACTUAL_USER}" git submodule update --init --recursive

#------------------------------------------------------------------------------
# Step 3: Build AuroraV7
#------------------------------------------------------------------------------
log_info "Step 3: Building AuroraV7..."

cd "${AURORA_DIR}"
sudo -u "${ACTUAL_USER}" mkdir -p build
cd build

# CMake will automatically build rpi-rgb-led-matrix on ARM
sudo -u "${ACTUAL_USER}" cmake ..
sudo -u "${ACTUAL_USER}" make -j${NUM_CORES}

#------------------------------------------------------------------------------
# Step 4: Setup systemd service
#------------------------------------------------------------------------------
log_info "Step 4: Setting up systemd service..."

SERVICE_FILE="/etc/systemd/system/aurorav7.service"

cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=AuroraV7 LED Matrix Driver
After=network.target

[Service]
ExecStart=${AURORA_DIR}/build/AuroraMatrix ${CONFIG_FILE}
Type=simple
WorkingDirectory=${AURORA_DIR}/build
Nice=-20
User=root
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable aurorav7
log_info "Systemd service installed and enabled"

#------------------------------------------------------------------------------
# Step 5: Configure system for LED matrix
#------------------------------------------------------------------------------
log_info "Step 5: Configuring system for LED matrix..."

# Find config.txt
if [ -f /boot/firmware/config.txt ]; then
    CONFIG_TXT="/boot/firmware/config.txt"
elif [ -f /boot/config.txt ]; then
    CONFIG_TXT="/boot/config.txt"
else
    CONFIG_TXT=""
    log_warn "Could not find config.txt, skipping system configuration"
fi

if [ -n "${CONFIG_TXT}" ]; then
    # Disable onboard audio (conflicts with LED matrix GPIO)
    if ! grep -q "^dtparam=audio=off" "${CONFIG_TXT}"; then
        echo "dtparam=audio=off" >> "${CONFIG_TXT}"
        log_info "Disabled onboard audio"
    fi

    # Set GPU memory
    if ! grep -q "^gpu_mem=" "${CONFIG_TXT}"; then
        echo "gpu_mem=128" >> "${CONFIG_TXT}"
        log_info "Set GPU memory to 128MB"
    fi
fi

#------------------------------------------------------------------------------
# Step 6: Start service (optional)
#------------------------------------------------------------------------------
if [ "${START_SERVICE}" = true ]; then
    log_info "Step 6: Starting aurorav7 service..."
    systemctl start aurorav7 || log_warn "Service failed to start - may need reboot first"
    sleep 2
    systemctl status aurorav7 --no-pager || true
else
    log_info "Step 6: Skipping service start (--no-start specified)"
fi

#------------------------------------------------------------------------------
# Done!
#------------------------------------------------------------------------------
log_info ""
log_info "=============================================="
log_info "Installation complete!"
log_info "=============================================="
log_info ""
log_info "Binaries: ${AURORA_DIR}/build/"
log_info "  - AuroraMatrix: LED matrix server"
log_info "  - AuroraPatternGen: Pattern generator"
log_info ""
log_info "Service commands:"
log_info "  sudo systemctl status aurorav7"
log_info "  sudo systemctl start aurorav7"
log_info "  sudo systemctl stop aurorav7"
log_info "  sudo journalctl -u aurorav7 -f"
log_info ""
log_info "IMPORTANT: Reboot to apply GPIO/audio changes:"
log_info "  sudo reboot"
