#!/bin/bash
# Install Aurora Web on Raspberry Pi / Debian
# Run as: ./install-aurora-web.sh (will prompt for sudo when needed)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=== Aurora Web Installer ==="
echo ""

# Stop and remove old C++ service if it exists
if systemctl list-unit-files | grep -q aurorav7.service; then
    echo "Stopping old aurorav7 service..."
    sudo systemctl stop aurorav7 2>/dev/null || true
    sudo systemctl disable aurorav7 2>/dev/null || true
    sudo rm -f /etc/systemd/system/aurorav7.service
    echo "Old service removed."
fi

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Install Python 3.11 if not present (Ubuntu 24.04 ships with 3.12)
if ! command -v python3.11 &> /dev/null; then
    echo "Installing Python 3.11..."
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get install -y -qq python3.11 python3.11-venv python3.11-dev
fi

# Install build dependencies for picamera2
echo ""
echo "Installing system dependencies..."
sudo apt-get install -y -qq libcap-dev

# Install libcamera v0.5 Python bindings (has PiSP IPA for Pi 5)
# On Ubuntu 24.04, the Pi repo package has a python3 (<3.12) dependency
# that must be force-installed since the system python3 is 3.12
if ! python3.11 -c "import libcamera" 2>/dev/null; then
    echo "Installing libcamera v0.5 Python bindings..."
    cd /tmp
    apt-get download python3-libcamera 2>/dev/null || true
    sudo dpkg --force-depends -i python3-libcamera_*.deb 2>/dev/null || true
    cd "$SCRIPT_DIR/.."
fi

# Create venv and install Python dependencies
echo ""
echo "Installing Python dependencies..."
cd "$SCRIPT_DIR/.."
uv venv --python 3.11 --clear
uv pip install -e .
uv pip install picamera2

# Symlink system libcamera bindings and KMS stub into venv
SITE_PKGS=".venv/lib/python3.11/site-packages"
ln -sf /usr/lib/python3/dist-packages/libcamera "$SITE_PKGS/libcamera"
ln -sf "$(pwd)/stubs/kms" "$SITE_PKGS/kms"

# Copy service file
echo ""
echo "Installing systemd service..."
sudo cp "$SCRIPT_DIR/aurora-web.service" /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable aurora-web
sudo systemctl restart aurora-web

# Install shairport-sync (AirPlay receiver)
echo ""
echo "Installing shairport-sync (AirPlay)..."
sudo apt-get install -y -qq shairport-sync

# Configure shairport-sync: device name + pipe backend for audio analysis
SHAIRPORT_CONF="/etc/shairport-sync.conf"
if [ -f "$SHAIRPORT_CONF" ]; then
    # Write a clean config with pipe output for Aurora audio feed
    sudo tee "$SHAIRPORT_CONF" > /dev/null <<'SHAIRPORT_EOF'
general = {
  name = "Aurora";
  output_backend = "pipe";
};

pipe = {
  name = "/tmp/shairport-audio";
};
SHAIRPORT_EOF
    echo "Configured shairport-sync with pipe backend"
fi

# Create the audio FIFO
[ -p /tmp/shairport-audio ] || mkfifo /tmp/shairport-audio
chmod 666 /tmp/shairport-audio

sudo systemctl enable shairport-sync
sudo systemctl restart shairport-sync

echo ""
echo "=== Aurora Web installed! ==="
echo ""
echo "Access at: http://$(hostname -I | awk '{print $1}')"
echo "AirPlay:   \"Aurora\" should appear on Apple devices"
echo ""
echo "Commands:"
echo "  sudo systemctl status aurora-web    # Check status"
echo "  sudo journalctl -u aurora-web -f    # View logs"
echo "  sudo systemctl restart aurora-web   # Restart"
echo "  sudo systemctl status shairport-sync  # AirPlay status"
