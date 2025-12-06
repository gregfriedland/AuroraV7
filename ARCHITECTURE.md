# AuroraV7 Web Architecture

## Overview

This document describes the architecture for adding a web interface to AuroraV7, enabling:
- Real-time drawer control and settings adjustment
- Custom Python drawers created via web UI
- Finger paint mode for interactive drawing
- User profiles with saved custom drawers

## Architecture: Python Web Server (Option A)

Single Python process handles web serving, pattern generation, and serial output.

```
┌──────────────────────────────────────────────────────────────────┐
│                         Web Browser                               │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Drawer List  │  │ Finger Paint │  │ Python Code Editor     │  │
│  │ + Settings   │  │   Canvas     │  │ (CodeMirror)           │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬────────────┘  │
└─────────┼─────────────────┼──────────────────────┼───────────────┘
          │                 │                      │
          │ HTTP            │ WebSocket            │ HTTP
          │ REST API        │ Real-time            │ REST API
          │                 │                      │
┌─────────▼─────────────────▼──────────────────────▼───────────────┐
│                    Python Server (FastAPI)                        │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                     Main Event Loop                          │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │ │
│  │  │ HTTP Routes │  │ WebSocket   │  │ Pattern Gen Loop    │  │ │
│  │  │ /api/*      │  │ Handler     │  │ (async, 40fps)      │  │ │
│  │  └─────────────┘  └──────┬──────┘  └──────────┬──────────┘  │ │
│  │                          │                    │              │ │
│  │                          ▼                    ▼              │ │
│  │                   ┌──────────────────────────────┐           │ │
│  │                   │      Drawer Manager          │           │ │
│  │                   │  - Built-in drawers (Python) │           │ │
│  │                   │  - Custom drawers (from YAML)│           │ │
│  │                   │  - Finger paint buffer       │           │ │
│  │                   └──────────────┬───────────────┘           │ │
│  └──────────────────────────────────┼───────────────────────────┘ │
│                                     │                             │
│  ┌──────────────────────────────────▼───────────────────────────┐ │
│  │                    Serial Output                              │ │
│  │  - Frame buffer → RGB bytes → Serial port                    │ │
│  │  - Snake pattern handling                                     │ │
│  │  - Gamma correction                                           │ │
│  └──────────────────────────────────┬───────────────────────────┘ │
└─────────────────────────────────────┼────────────────────────────┘
                                      │
                                      │ Serial (115200 baud)
                                      ▼
                          ┌───────────────────────┐
                          │   Teensy + LED Strip  │
                          │   (32x18 WS2801)      │
                          └───────────────────────┘
```

## Components

### 1. Web Server (FastAPI)

**Why FastAPI:**
- Native async/await (important for real-time)
- Built-in WebSocket support
- Auto-generated OpenAPI docs
- Type hints and validation
- Lightweight, fast startup

**File structure:**
```
aurora_web/
├── main.py              # FastAPI app, entry point
├── api/
│   ├── __init__.py
│   ├── drawers.py       # Drawer CRUD endpoints
│   ├── settings.py      # Settings endpoints
│   └── users.py         # User profile endpoints
├── core/
│   ├── __init__.py
│   ├── drawer_manager.py    # Manages active drawer
│   ├── pattern_loop.py      # Main 40fps render loop
│   ├── serial_output.py     # Serial port handling
│   └── palette.py           # Color palette generation
├── drawers/
│   ├── __init__.py
│   ├── base.py          # Base Drawer class
│   ├── bzr.py           # Bzr reaction-diffusion
│   ├── alien_blob.py    # Perlin noise blobs
│   ├── gray_scott.py    # Gray-Scott reaction-diffusion
│   ├── ginzburg_landau.py
│   ├── finger_paint.py  # Interactive drawing
│   └── custom.py        # Loads/runs YAML custom drawers
├── static/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── custom_drawers/      # User-created drawers (YAML)
│   └── greg/
│       └── my_waves.yaml
└── config.yaml          # Server configuration
```

### 2. REST API Endpoints

```
GET  /api/drawers                    # List all drawers (built-in + custom)
GET  /api/drawers/:name              # Get drawer info + settings schema
POST /api/drawers/active             # Set active drawer {"name": "Bzr"}
GET  /api/drawers/active/settings    # Get current drawer settings
PUT  /api/drawers/active/settings    # Update settings {"speed": 50, ...}

GET  /api/users                      # List user profiles
POST /api/users                      # Create user profile
GET  /api/users/:id/drawers          # List user's custom drawers
POST /api/users/:id/drawers          # Save new custom drawer
PUT  /api/users/:id/drawers/:name    # Update custom drawer
DELETE /api/users/:id/drawers/:name  # Delete custom drawer

GET  /api/palettes                   # List available palettes
POST /api/palettes/active            # Set active palette

GET  /api/status                     # Current fps, drawer, etc.
```

### 3. WebSocket Protocol

**Endpoint:** `ws://host:8000/ws`

**Client → Server messages:**
```json
// Finger paint - draw at coordinates
{"type": "paint", "x": 15, "y": 8, "color": [255, 0, 0], "radius": 2}

// Clear finger paint canvas
{"type": "clear"}

// Request frame preview
{"type": "subscribe_preview", "enabled": true, "fps": 10}
```

**Server → Client messages:**
```json
// Status update (sent on change)
{"type": "status", "drawer": "Bzr", "fps": 39.8, "palette": 42}

// Frame preview (if subscribed, downscaled)
{"type": "preview", "width": 32, "height": 18, "data": "base64..."}

// Drawer changed
{"type": "drawer_changed", "name": "GrayScott", "settings": {...}}
```

### 4. Custom Drawer Format (YAML)

```yaml
# custom_drawers/greg/plasma_waves.yaml
name: "Plasma Waves"
author: "greg"
description: "Colorful plasma effect with sine waves"
created: 2025-12-06
updated: 2025-12-06

settings:
  speed:
    type: int
    default: 50
    min: 1
    max: 100
    description: "Animation speed"
  scale:
    type: float
    default: 0.1
    min: 0.01
    max: 1.0
    description: "Wave scale (smaller = more detail)"
  color_cycle:
    type: int
    default: 20
    min: 0
    max: 100
    description: "Color cycling speed"

# Python code executed each frame
# Available: numpy as np, math, width, height, frame_num, settings, palette
# Must return: 2D array of palette indices (height, width) dtype=int
code: |
  import numpy as np

  def draw(width, height, frame_num, settings, palette_size):
      t = frame_num * settings['speed'] / 1000.0
      scale = settings['scale']

      # Create coordinate grids
      x = np.arange(width) * scale
      y = np.arange(height) * scale
      xx, yy = np.meshgrid(x, y)

      # Plasma formula
      v1 = np.sin(xx + t)
      v2 = np.sin(yy + t * 0.5)
      v3 = np.sin((xx + yy + t) * 0.5)
      v4 = np.sin(np.sqrt(xx**2 + yy**2) + t)

      plasma = (v1 + v2 + v3 + v4) / 4.0  # -1 to 1

      # Map to palette indices
      indices = ((plasma + 1) * 0.5 * (palette_size - 1)).astype(np.int32)
      indices += int(frame_num * settings['color_cycle'] / 10)

      return indices % palette_size
```

### 5. Drawer Base Class (Python)

```python
# aurora_web/drawers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Tuple
import numpy as np

@dataclass
class SettingDef:
    type: str  # 'int', 'float', 'bool'
    default: Any
    min: Any = None
    max: Any = None
    description: str = ""

class Drawer(ABC):
    name: str = "Base"
    description: str = ""

    def __init__(self, width: int, height: int, palette_size: int):
        self.width = width
        self.height = height
        self.palette_size = palette_size
        self.frame_num = 0
        self.settings = self._default_settings()

    @classmethod
    @abstractmethod
    def settings_schema(cls) -> Dict[str, SettingDef]:
        """Return settings schema for this drawer"""
        pass

    def _default_settings(self) -> Dict[str, Any]:
        return {k: v.default for k, v in self.settings_schema().items()}

    def update_settings(self, settings: Dict[str, Any]):
        for k, v in settings.items():
            if k in self.settings:
                self.settings[k] = v

    @abstractmethod
    def draw(self) -> np.ndarray:
        """
        Generate one frame.
        Returns: 2D numpy array of palette indices, shape (height, width)
        """
        pass

    def step(self) -> np.ndarray:
        """Advance one frame and return result"""
        result = self.draw()
        self.frame_num += 1
        return result

    def reset(self):
        """Reset drawer state"""
        self.frame_num = 0
```

### 6. Pattern Generation Loop

```python
# aurora_web/core/pattern_loop.py
import asyncio
import numpy as np
from typing import Optional

class PatternLoop:
    def __init__(self, drawer_manager, serial_output, fps: int = 40):
        self.drawer_manager = drawer_manager
        self.serial_output = serial_output
        self.target_fps = fps
        self.running = False
        self.actual_fps = 0.0

    async def run(self):
        self.running = True
        frame_time = 1.0 / self.target_fps
        fps_counter = FpsCounter()

        while self.running:
            start = asyncio.get_event_loop().time()

            # Get current drawer and generate frame
            drawer = self.drawer_manager.active_drawer
            if drawer:
                # Generate palette indices
                indices = drawer.step()

                # Apply finger paint overlay if active
                indices = self.drawer_manager.apply_finger_paint(indices)

                # Convert to RGB via palette
                rgb = self.drawer_manager.palette.indices_to_rgb(indices)

                # Apply gamma correction
                rgb = self.apply_gamma(rgb)

                # Send to serial
                self.serial_output.send_frame(rgb)

            # FPS tracking
            self.actual_fps = fps_counter.tick()

            # Sleep to maintain target FPS
            elapsed = asyncio.get_event_loop().time() - start
            sleep_time = max(0, frame_time - elapsed)
            await asyncio.sleep(sleep_time)

    def stop(self):
        self.running = False
```

### 7. Serial Output

```python
# aurora_web/core/serial_output.py
import serial
import numpy as np

class SerialOutput:
    def __init__(self, device: str, width: int, height: int,
                 baud: int = 115200, layout_left_to_right: bool = True):
        self.device = device
        self.width = width
        self.height = height
        self.layout_ltr = layout_left_to_right
        self.serial = None

    def connect(self):
        if self.device:
            self.serial = serial.Serial(self.device, 115200)

    def close(self):
        if self.serial:
            self.serial.close()

    def send_frame(self, rgb: np.ndarray):
        """
        rgb: numpy array shape (height, width, 3), dtype uint8
        """
        if not self.serial:
            return

        # Apply snake pattern (alternate rows reversed)
        frame = rgb.copy()
        for y in range(self.height):
            if self.layout_ltr:
                if y % 2 == 1:
                    frame[y, :, :] = frame[y, ::-1, :]
            else:
                if y % 2 == 0:
                    frame[y, :, :] = frame[y, ::-1, :]

        # Flatten and cap at 254 (255 is delimiter)
        data = np.clip(frame.flatten(), 0, 254).astype(np.uint8)

        # Add delimiter and send
        self.serial.write(bytes(data) + b'\xff')
```

### 8. Web Client

Simple HTML/JS interface:

```html
<!-- static/index.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Aurora Control</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>Aurora</h1>
            <span id="status">Connecting...</span>
        </header>

        <nav id="tabs">
            <button data-tab="drawers" class="active">Drawers</button>
            <button data-tab="paint">Finger Paint</button>
            <button data-tab="create">Create</button>
        </nav>

        <main>
            <!-- Drawer selection and settings -->
            <section id="drawers" class="tab-content active">
                <select id="drawer-select"></select>
                <div id="settings-panel"></div>
            </section>

            <!-- Finger paint canvas -->
            <section id="paint" class="tab-content">
                <canvas id="paint-canvas"></canvas>
                <div id="paint-tools">
                    <input type="color" id="paint-color" value="#ff0000">
                    <input type="range" id="brush-size" min="1" max="10" value="2">
                    <button id="clear-paint">Clear</button>
                </div>
            </section>

            <!-- Custom drawer editor -->
            <section id="create" class="tab-content">
                <input id="drawer-name" placeholder="Drawer name">
                <div id="code-editor"></div>
                <button id="save-drawer">Save</button>
                <button id="test-drawer">Test</button>
            </section>
        </main>

        <!-- Live preview -->
        <aside id="preview">
            <canvas id="preview-canvas"></canvas>
            <span id="fps">0 fps</span>
        </aside>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/python/python.min.js"></script>
    <script src="app.js"></script>
</body>
</html>
```

## Security Considerations

### Custom Code Execution

User-submitted Python code needs sandboxing:

1. **RestrictedPython** - Parse and transform code to restrict operations
2. **Limited globals** - Only allow numpy, math, safe builtins
3. **Timeout** - Kill execution if >100ms per frame
4. **No imports** - Pre-import allowed modules

```python
# aurora_web/drawers/custom.py
from RestrictedPython import compile_restricted
import numpy as np

ALLOWED_GLOBALS = {
    '__builtins__': {
        'range': range,
        'len': len,
        'min': min,
        'max': max,
        'abs': abs,
        'int': int,
        'float': float,
        'sum': sum,
    },
    'np': np,
    'math': __import__('math'),
}

def execute_custom_drawer(code: str, width: int, height: int,
                          frame_num: int, settings: dict, palette_size: int):
    # Compile with restrictions
    byte_code = compile_restricted(code, '<custom>', 'exec')

    # Execute in sandbox
    local_vars = {}
    exec(byte_code, ALLOWED_GLOBALS, local_vars)

    # Call the draw function
    if 'draw' not in local_vars:
        raise ValueError("Custom drawer must define draw() function")

    return local_vars['draw'](width, height, frame_num, settings, palette_size)
```

## Deployment

### Systemd Service

```ini
# /etc/systemd/system/aurora-web.service
[Unit]
Description=Aurora Web Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 -m aurora_web.main --config /home/debian/AuroraV7/config/serial-matrix-32x18.json
WorkingDirectory=/home/debian/AuroraV7
User=debian
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Configuration

```yaml
# aurora_web/config.yaml
server:
  host: "0.0.0.0"
  port: 8000

matrix:
  width: 32
  height: 18
  serial_device: "/dev/ttyACM0"
  layout_left_to_right: true
  fps: 40
  gamma: 2.5

palette:
  size: 4096
  base_colors_per_palette: 5

drawers:
  default: "Bzr"
  change_interval: 30  # seconds, 0 to disable auto-change

custom_drawers_path: "./custom_drawers"
users_db: "./users.yaml"
```

## Migration Path

1. **Phase 1**: Python web server with finger paint only
   - Keep C++ pattern gen running
   - Web server sends paint commands via file/socket

2. **Phase 2**: Port one drawer to Python (Bzr or AlienBlob)
   - Test performance on Pi

3. **Phase 3**: Port remaining drawers
   - Add custom drawer support

4. **Phase 4**: Full transition
   - Retire C++ pattern gen
   - Single Python process

## Performance Notes

- NumPy vectorized operations are fast enough for 40fps on Pi
- Gray-Scott may need numba JIT for acceptable performance
- Finger paint overlay is O(1) with numpy boolean indexing
- WebSocket overhead is negligible at 1-2 clients
