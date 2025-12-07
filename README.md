# AuroraV7

LED matrix control software with a Python web interface for pattern generation, finger painting, and audio/video reactive visualizations.

## Features

- **Pattern Drawers**: Multiple visual pattern generators (AlienBlob, Bzr, GrayScott, GinzburgLandau)
- **Finger Paint**: Draw on the LED matrix via web browser
- **Audio Reactive**: Beat detection and spectrum analysis for music-reactive patterns
- **Video Input**: Motion detection and light-level reactive patterns
- **Custom Drawers**: Create your own patterns with Python code via YAML definitions
- **User Profiles**: Save preferences and custom drawers per user
- **Web Interface**: Control everything from any browser

## Requirements

- Python 3.10+
- Raspberry Pi (or any Linux machine with serial port access to LED controller)
- LED matrix with serial interface (e.g., Teensy + WS2801 strips)

## Installation

### Quick Install (Raspberry Pi)

```bash
# Clone the repository
git clone https://github.com/gregfriedland/AuroraV7.git
cd AuroraV7

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Install systemd service
sudo ./install/install-aurora-web.sh
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/gregfriedland/AuroraV7.git
cd AuroraV7

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Or install with uv (faster)
uv pip install -e .
```

## Configuration

Edit `aurora_web/config.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 80

matrix:
  width: 32
  height: 18
  serial_device: "/dev/ttyACM0"
  fps: 40
  gamma: 2.5
  layout_left_to_right: true

inputs:
  audio:
    enabled: true
    source: "pulse"  # or "alsa:hw:0"

  video:
    enabled: false
    device: 0
```

## Running

### Development

```bash
source .venv/bin/activate
python -m uvicorn aurora_web.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production (Systemd)

```bash
# Start service
sudo systemctl start aurora-web

# Check status
sudo systemctl status aurora-web

# View logs
sudo journalctl -u aurora-web -f

# Enable on boot
sudo systemctl enable aurora-web
```

Then open `http://aurora.local` (or Pi's IP address) in a browser.

## Project Structure

```
AuroraV7/
├── aurora_web/              # Python web application
│   ├── main.py              # FastAPI app entry point
│   ├── config.yaml          # Configuration file
│   ├── core/                # Core components
│   │   ├── drawer_manager.py
│   │   ├── palette.py
│   │   ├── serial_process.py
│   │   ├── shared_frame.py
│   │   └── users.py
│   ├── drawers/             # Pattern generators
│   │   ├── base.py
│   │   ├── alien_blob.py
│   │   ├── bzr.py
│   │   ├── gray_scott.py
│   │   ├── ginzburg_landau.py
│   │   ├── custom.py
│   │   └── off.py
│   ├── inputs/              # Input feeds
│   │   ├── audio_feed.py
│   │   ├── video_feed.py
│   │   └── canvas_feed.py
│   ├── api/                 # REST API endpoints
│   │   ├── users.py
│   │   └── custom_drawers.py
│   ├── static/              # Web UI files
│   └── custom_drawers/      # User-created patterns
├── install/                 # Installation scripts
│   ├── aurora-web.service
│   └── install-aurora-web.sh
├── firmware/                # Teensy/Arduino firmware
│   └── AuroraLEDs.ino
├── config/                  # Example configurations
└── pyproject.toml           # Python package config
```

## Creating Custom Drawers

Create a YAML file in `aurora_web/custom_drawers/username/`:

```yaml
name: "My Pattern"
author: "username"
description: "A custom pattern"

settings:
  speed:
    type: float
    default: 1.0
    min: 0.1
    max: 5.0

code: |
  def draw(width, height, ctx, settings, palette_size):
      t = ctx.time * settings['speed']

      xx, yy = np.meshgrid(np.arange(width), np.arange(height))
      pattern = np.sin(xx * 0.1 + t) * np.cos(yy * 0.1 + t)

      normalized = (pattern + 1) / 2
      indices = (normalized * (palette_size - 1)).astype(np.int32)

      return indices % palette_size
```

## API Endpoints

- `GET /api/config` - Get matrix configuration
- `GET /api/drawers` - List available drawers
- `GET /api/status` - Get current status
- `WebSocket /ws` - Real-time frame streaming and control

### User API
- `POST /api/users/register` - Create account
- `POST /api/users/login` - Login
- `GET /api/users/me` - Get profile

### Custom Drawer API
- `GET /api/custom-drawers/list` - List custom drawers
- `POST /api/custom-drawers/create` - Create new drawer
- `GET /api/custom-drawers/template` - Get example template

## Testing

```bash
# Run all tests
pytest aurora_web/tests/ -v

# Run specific test file
pytest aurora_web/tests/test_drawers.py -v
```

## Hardware Setup

### LED Matrix with Teensy

The system expects a Teensy microcontroller connected via USB serial, receiving RGB data for a snake-pattern LED matrix.

See `firmware/AuroraLEDs.ino` for the Teensy firmware.

### Serial Protocol

- Baud rate: 115200
- Frame format: RGB bytes (capped at 254) + 0xFF delimiter
- Snake pattern: alternate rows reversed

## License

MIT License - See LICENSE file.
