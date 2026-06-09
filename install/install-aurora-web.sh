#!/bin/bash
# Install Aurora Web on Raspberry Pi / Debian
# Run as: ./install-aurora-web.sh (will prompt for sudo when needed)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=== Aurora Web Installer ==="
echo ""

RGB_MATRIX_REPO="https://github.com/hzeller/rpi-rgb-led-matrix.git"
RGB_MATRIX_DIR="${RGB_MATRIX_DIR:-$HOME/.local/src/rpi-rgb-led-matrix}"

# Stop and remove old C++ service if it exists
if systemctl list-unit-files | grep -q aurorav7.service; then
    echo "Stopping old aurorav7 service..."
    sudo systemctl stop aurorav7 2>/dev/null || true
    sudo systemctl disable aurorav7 2>/dev/null || true
    sudo rm -f /etc/systemd/system/aurorav7.service
    echo "Old service removed."
fi

# Install system dependencies
echo ""
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y git python3-dev cython3 build-essential

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create venv and install Python dependencies
echo ""
echo "Installing Python dependencies..."
cd "$SCRIPT_DIR/.."
uv venv --python 3.11 2>/dev/null || uv venv
uv pip install -e .

# Install rpi-rgb-led-matrix Python bindings for direct HUB75 output.
echo ""
echo "Installing rpi-rgb-led-matrix Python bindings..."
mkdir -p "$(dirname "$RGB_MATRIX_DIR")"
if [ -d "$RGB_MATRIX_DIR/.git" ]; then
    git -C "$RGB_MATRIX_DIR" fetch --depth 1 origin master
    git -C "$RGB_MATRIX_DIR" checkout master
    git -C "$RGB_MATRIX_DIR" reset --hard origin/master
else
    git clone --depth 1 "$RGB_MATRIX_REPO" "$RGB_MATRIX_DIR"
fi
uv pip install "$RGB_MATRIX_DIR/bindings/python"

# Copy service file
echo ""
echo "Installing systemd service..."
sudo cp "$SCRIPT_DIR/aurora-web.service" /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable aurora-web
sudo systemctl restart aurora-web

echo ""
echo "=== Aurora Web installed! ==="
echo ""
echo "Access at: http://$(hostname -I | awk '{print $1}')"
echo ""
echo "Commands:"
echo "  sudo systemctl status aurora-web    # Check status"
echo "  sudo journalctl -u aurora-web -f    # View logs"
echo "  sudo systemctl restart aurora-web   # Restart"
