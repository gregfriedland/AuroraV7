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

# Create venv and install Python dependencies
echo ""
echo "Installing Python dependencies..."
cd "$SCRIPT_DIR/.."
uv venv --python 3.11 2>/dev/null || uv venv
uv pip install fastapi "uvicorn[standard]" websockets pyyaml numpy pyserial

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
