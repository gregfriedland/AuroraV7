# AuroraV7 Web Architecture

## Overview

This document describes the architecture for adding a web interface to AuroraV7, enabling:
- Real-time drawer control and settings adjustment
- Custom Python drawers created via web UI
- Finger paint mode for interactive drawing
- User profiles with saved custom drawers
- Audio-reactive patterns (BPM, beat detection)
- Video input processing (motion, light level)

## Architecture: Python Web Server (Option A)

Two-process architecture: Main process handles web/pattern generation, separate process handles serial output for zero-lag display.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              Web Browser                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────────┐  │
│  │ Drawer List  │  │ Finger Paint │  │ Python Code Editor             │  │
│  │ + Settings   │  │   Canvas     │  │ (CodeMirror)                   │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬────────────────────┘  │
└─────────┼─────────────────┼──────────────────────┼───────────────────────┘
          │ HTTP            │ WebSocket            │ HTTP
          ▼                 ▼                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     MAIN PROCESS (FastAPI)                                │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                        Input Feeds                                   │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │ │
│  │  │ Audio Feed  │  │ Video Feed  │  │ Canvas Feed                 │  │ │
│  │  │ - bpm       │  │ - frame     │  │ - touch events              │  │ │
│  │  │ - onset     │  │ - motion    │  │ - paint buffer              │  │ │
│  │  │ - spectrum  │  │ - light_lvl │  │                             │  │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────────────┬──────────────┘  │ │
│  │         │                │                        │                  │ │
│  │         └────────────────┼────────────────────────┘                  │ │
│  │                          ▼                                           │ │
│  │                 ┌─────────────────┐                                  │ │
│  │                 │  InputContext   │  (passed to every drawer)        │ │
│  │                 └────────┬────────┘                                  │ │
│  │                          │                                           │ │
│  │  ┌───────────────────────▼───────────────────────────────────────┐  │ │
│  │  │                    Pattern Gen Loop (40fps)                    │  │ │
│  │  │                                                                │  │ │
│  │  │   drawer.draw(context: InputContext) → palette_indices        │  │ │
│  │  │                          │                                     │  │ │
│  │  │                          ▼                                     │  │ │
│  │  │              palette.to_rgb(indices) → rgb_frame               │  │ │
│  │  └───────────────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                     │                                     │
│                                     │ Shared Memory (frame buffer)        │
│                                     ▼                                     │
└─────────────────────────────────────┼─────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────────┐
          │                           │                               │
          │     SERIAL PROCESS        │                               │
          │     (separate Python)     │                               │
          │                           ▼                               │
          │  ┌─────────────────────────────────────────────────────┐  │
          │  │              Frame Consumer Loop                     │  │
          │  │  - Reads from shared memory                         │  │
          │  │  - Applies gamma correction                         │  │
          │  │  - Applies snake pattern                            │  │
          │  │  - Writes to serial at consistent rate              │  │
          │  └──────────────────────────┬──────────────────────────┘  │
          │                             │                             │
          └─────────────────────────────┼─────────────────────────────┘
                                        │
                                        │ Serial (115200 baud)
                                        ▼
                            ┌───────────────────────┐
                            │   Teensy + LED Strip  │
                            │   (32x18 WS2801)      │
                            └───────────────────────┘
```

## Input Feeds

### InputContext - Passed to All Drawers

Every drawer receives an `InputContext` object each frame with optional input data:

```python
@dataclass
class AudioInput:
    """Audio analysis data - all fields optional"""
    bpm: float | None = None              # Current tempo (60-200)
    beat_onset: bool = False              # True on beat hit
    beat_phase: float = 0.0               # 0.0-1.0 position within beat
    spectrum: np.ndarray | None = None    # FFT bins (e.g., 16 bands)
    volume: float = 0.0                   # 0.0-1.0 current volume level
    bass: float = 0.0                     # 0.0-1.0 low frequency energy
    mids: float = 0.0                     # 0.0-1.0 mid frequency energy
    highs: float = 0.0                    # 0.0-1.0 high frequency energy

@dataclass
class VideoInput:
    """Video/camera analysis data - all fields optional"""
    frame: np.ndarray | None = None       # Current camera frame (RGB)
    motion_amount: float = 0.0            # 0.0-1.0 overall motion level
    motion_map: np.ndarray | None = None  # Per-pixel motion intensity
    light_level: float = 0.5              # 0.0-1.0 average brightness
    faces: list[Rect] | None = None       # Detected face regions
    dominant_color: tuple[int,int,int] | None = None  # Most common color

@dataclass
class CanvasInput:
    """Touch/paint input - updated via WebSocket"""
    touches: list[Touch] = field(default_factory=list)  # Active touch points
    paint_buffer: np.ndarray | None = None  # Accumulated paint (height, width, 4) RGBA
    last_touch: Touch | None = None         # Most recent touch event

@dataclass
class Touch:
    x: float          # 0.0-1.0 normalized x position
    y: float          # 0.0-1.0 normalized y position
    pressure: float   # 0.0-1.0 pressure (1.0 for mouse)
    radius: float     # Touch radius in pixels
    color: tuple[int, int, int] = (255, 255, 255)

@dataclass
class InputContext:
    """All inputs available to drawers each frame"""
    frame_num: int
    time: float                    # Seconds since start
    delta_time: float              # Seconds since last frame

    audio: AudioInput              # Audio analysis (may be empty)
    video: VideoInput              # Video analysis (may be empty)
    canvas: CanvasInput            # Touch/paint input

    # Convenience properties
    @property
    def has_audio(self) -> bool:
        return self.audio.bpm is not None

    @property
    def has_video(self) -> bool:
        return self.video.frame is not None

    @property
    def has_touch(self) -> bool:
        return len(self.canvas.touches) > 0
```

## Components

### 1. File Structure

```
aurora_web/
├── main.py                  # FastAPI app, spawns serial process
├── api/
│   ├── __init__.py
│   ├── drawers.py           # Drawer CRUD endpoints
│   ├── settings.py          # Settings endpoints
│   └── users.py             # User profile endpoints
├── core/
│   ├── __init__.py
│   ├── drawer_manager.py    # Manages active drawer
│   ├── pattern_loop.py      # Main 40fps render loop
│   ├── serial_process.py    # Separate process for serial output
│   ├── shared_frame.py      # Shared memory frame buffer
│   ├── palette.py           # Color palette generation
│   └── input_context.py     # InputContext and related classes
├── inputs/
│   ├── __init__.py
│   ├── audio_feed.py        # Audio analysis (BPM, beats, FFT)
│   ├── video_feed.py        # Camera/video processing
│   └── canvas_feed.py       # Touch/paint handling
├── drawers/
│   ├── __init__.py
│   ├── base.py              # Base Drawer class
│   ├── bzr.py               # Bzr reaction-diffusion
│   ├── alien_blob.py        # Perlin noise blobs
│   ├── gray_scott.py        # Gray-Scott reaction-diffusion
│   ├── ginzburg_landau.py
│   ├── finger_paint.py      # Pure paint drawer
│   └── custom.py            # Loads/runs YAML custom drawers
├── static/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── custom_drawers/          # User-created drawers (YAML)
│   └── greg/
│       └── my_waves.yaml
└── config.yaml              # Server configuration
```

### 2. Drawer Base Class with InputContext

```python
# aurora_web/drawers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, ClassVar
import numpy as np

from aurora_web.core.input_context import InputContext

@dataclass
class SettingDef:
    type: str  # 'int', 'float', 'bool'
    default: Any
    min: Any = None
    max: Any = None
    description: str = ""

class Drawer(ABC):
    """Base class for all pattern drawers"""

    name: ClassVar[str] = "Base"
    description: ClassVar[str] = ""

    # Declare which inputs this drawer can use (for UI hints)
    uses_audio: ClassVar[bool] = False
    uses_video: ClassVar[bool] = False
    uses_canvas: ClassVar[bool] = False

    def __init__(self, width: int, height: int, palette_size: int):
        self.width = width
        self.height = height
        self.palette_size = palette_size
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
    def draw(self, ctx: InputContext) -> np.ndarray:
        """
        Generate one frame.

        Args:
            ctx: InputContext with audio, video, canvas, timing info

        Returns:
            2D numpy array of palette indices, shape (height, width), dtype int
        """
        pass

    def reset(self):
        """Reset drawer state"""
        pass


class AudioReactiveDrawer(Drawer):
    """Base for drawers that react to audio"""
    uses_audio: ClassVar[bool] = True

    def get_beat_intensity(self, ctx: InputContext) -> float:
        """Helper: returns 1.0 on beat, decays to 0.0"""
        if not ctx.has_audio:
            return 0.0
        if ctx.audio.beat_onset:
            self._beat_intensity = 1.0
        else:
            decay = 0.1 * ctx.delta_time * 60  # Decay over ~10 frames
            self._beat_intensity = max(0, getattr(self, '_beat_intensity', 0) - decay)
        return self._beat_intensity


class VideoReactiveDrawer(Drawer):
    """Base for drawers that use video input"""
    uses_video: ClassVar[bool] = True


class InteractiveDrawer(Drawer):
    """Base for drawers that respond to touch/canvas"""
    uses_canvas: ClassVar[bool] = True
```

### 3. Example: Audio-Reactive Bzr Drawer

```python
# aurora_web/drawers/bzr.py
import numpy as np
from aurora_web.drawers.base import AudioReactiveDrawer, SettingDef
from aurora_web.core.input_context import InputContext

class BzrDrawer(AudioReactiveDrawer):
    name = "Bzr"
    description = "Belousov-Zhabotinsky reaction simulation"
    uses_audio = True
    uses_canvas = True  # Can overlay paint

    PARAM_SETS = [
        {"ka": 0.5, "kb": 0.5, "kc": 0.6},
        {"ka": 1.1, "kb": 1.1, "kc": 0.9},
        # ... more param sets
    ]

    @classmethod
    def settings_schema(cls) -> Dict[str, SettingDef]:
        return {
            "speed": SettingDef("int", 50, 1, 100, "Animation speed"),
            "color_speed": SettingDef("int", 20, 0, 100, "Color cycling speed"),
            "zoom": SettingDef("int", 50, 0, 100, "Pattern zoom level"),
            "params": SettingDef("int", 0, 0, len(cls.PARAM_SETS)-1, "Parameter set"),
            "audio_reactivity": SettingDef("float", 0.5, 0, 1, "Audio influence"),
        }

    def __init__(self, width: int, height: int, palette_size: int):
        super().__init__(width, height, palette_size)
        self.a = np.random.rand(height, width)
        self.b = np.random.rand(height, width)
        self.c = np.random.rand(height, width)
        self.color_offset = 0

    def draw(self, ctx: InputContext) -> np.ndarray:
        # Get parameters
        params = self.PARAM_SETS[self.settings["params"]]
        ka, kb, kc = params["ka"], params["kb"], params["kc"]

        # Audio reactivity - boost speed on beats
        speed_mult = 1.0
        if ctx.has_audio and self.settings["audio_reactivity"] > 0:
            beat = self.get_beat_intensity(ctx)
            speed_mult = 1.0 + beat * self.settings["audio_reactivity"] * 2

        # Run simulation steps
        steps = int(self.settings["speed"] * speed_mult / 10)
        for _ in range(max(1, steps)):
            self._step_simulation(ka, kb, kc)

        # Apply canvas paint as disturbance
        if ctx.has_touch and ctx.canvas.paint_buffer is not None:
            paint = ctx.canvas.paint_buffer[:, :, 3] / 255.0  # Alpha as mask
            self.a = np.where(paint > 0.1, 1.0, self.a)

        # Convert to palette indices
        indices = (self.b * (self.palette_size - 1)).astype(np.int32)

        # Color cycling
        self.color_offset += self.settings["color_speed"]
        indices = (indices + self.color_offset) % self.palette_size

        return indices

    def _step_simulation(self, ka, kb, kc):
        # BZ reaction-diffusion step
        a_avg = self._neighbor_avg(self.a)
        b_avg = self._neighbor_avg(self.b)
        c_avg = self._neighbor_avg(self.c)

        self.a = np.clip(a_avg + self.a * (ka * self.b - kc * self.c), 0, 1)
        self.b = np.clip(b_avg + self.b * (kb * self.c - ka * self.a), 0, 1)
        self.c = np.clip(c_avg + self.c * (kc * self.a - kb * self.b), 0, 1)

    def _neighbor_avg(self, arr):
        return (np.roll(arr, 1, 0) + np.roll(arr, -1, 0) +
                np.roll(arr, 1, 1) + np.roll(arr, -1, 1)) / 4
```

### 4. Custom Drawer YAML Format (Updated)

```yaml
# custom_drawers/greg/beat_pulse.yaml
name: "Beat Pulse"
author: "greg"
description: "Pulses on beat with audio spectrum visualization"
created: 2025-12-06

# Declare input dependencies (for UI)
uses:
  audio: true
  video: false
  canvas: true

settings:
  base_speed:
    type: float
    default: 1.0
    min: 0.1
    max: 5.0
    description: "Base animation speed"

  beat_intensity:
    type: float
    default: 1.0
    min: 0
    max: 2.0
    description: "How much beats affect the pattern"

  spectrum_height:
    type: float
    default: 0.3
    min: 0
    max: 1.0
    description: "Height of spectrum bars (0 to disable)"

# Python code - receives InputContext
# Available: np, math, ctx (InputContext), width, height, settings, palette_size
code: |
  def draw(width, height, ctx, settings, palette_size):
      indices = np.zeros((height, width), dtype=np.int32)
      t = ctx.time * settings['base_speed']

      # Base gradient
      y_norm = np.linspace(0, 1, height)[:, np.newaxis]
      x_norm = np.linspace(0, 1, width)[np.newaxis, :]
      base = np.sin(x_norm * 4 + t) * np.cos(y_norm * 4 + t * 0.7)

      # Beat pulse - expand from center on beat
      if ctx.has_audio and ctx.audio.beat_onset:
          pulse = settings['beat_intensity']
      else:
          # Decay
          pulse = getattr(draw, '_pulse', 0) * 0.9
      draw._pulse = pulse

      cx, cy = width / 2, height / 2
      xx, yy = np.meshgrid(np.arange(width), np.arange(height))
      dist = np.sqrt((xx - cx)**2 + (yy - cy)**2)
      max_dist = np.sqrt(cx**2 + cy**2)

      # Pulse ring
      ring_pos = (pulse * max_dist) % max_dist
      ring = np.exp(-((dist - ring_pos) ** 2) / 20)

      # Spectrum bars at bottom
      if ctx.has_audio and ctx.audio.spectrum is not None and settings['spectrum_height'] > 0:
          spectrum = ctx.audio.spectrum
          num_bars = len(spectrum)
          bar_width = width // num_bars
          bar_max_height = int(height * settings['spectrum_height'])

          for i, val in enumerate(spectrum):
              bar_height = int(val * bar_max_height)
              x_start = i * bar_width
              x_end = min(x_start + bar_width - 1, width)
              y_start = height - bar_height
              indices[y_start:, x_start:x_end] += int(val * palette_size * 0.3)

      # Combine
      combined = base * 0.5 + ring * 0.5
      indices += ((combined + 1) * 0.5 * (palette_size - 1)).astype(np.int32)

      # Canvas overlay
      if ctx.canvas.paint_buffer is not None:
          paint_alpha = ctx.canvas.paint_buffer[:, :, 3] / 255.0
          paint_idx = (ctx.canvas.paint_buffer[:, :, 0].astype(np.int32) * palette_size // 256)
          indices = np.where(paint_alpha > 0.1, paint_idx, indices)

      return indices % palette_size
```

### 5. Input Feed Implementations

```python
# aurora_web/inputs/audio_feed.py
import numpy as np
import asyncio
from dataclasses import dataclass
from typing import Optional
import subprocess
import struct

class AudioFeed:
    """Captures and analyzes audio for beat detection and spectrum"""

    def __init__(self, source: str = "pulse", sample_rate: int = 44100):
        self.source = source
        self.sample_rate = sample_rate
        self.bpm: Optional[float] = None
        self.beat_onset: bool = False
        self.spectrum: Optional[np.ndarray] = None
        self._last_beat_time: float = 0
        self._beat_intervals: list[float] = []
        self._process: Optional[subprocess.Popen] = None

    async def start(self):
        """Start audio capture (e.g., from PulseAudio or ALSA)"""
        # Example: capture from default audio device
        self._process = await asyncio.create_subprocess_exec(
            "parec", "--format=s16le", "--rate=44100", "--channels=1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        """Read audio data and analyze"""
        buffer_size = 1024
        while self._process and self._process.returncode is None:
            data = await self._process.stdout.read(buffer_size * 2)
            if data:
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768
                self._analyze(samples)
            await asyncio.sleep(0.01)

    def _analyze(self, samples: np.ndarray):
        """Compute spectrum and detect beats"""
        # FFT for spectrum
        fft = np.abs(np.fft.rfft(samples))
        # Reduce to 16 bands
        bands = 16
        band_size = len(fft) // bands
        self.spectrum = np.array([
            np.mean(fft[i*band_size:(i+1)*band_size])
            for i in range(bands)
        ])
        self.spectrum = self.spectrum / (np.max(self.spectrum) + 1e-6)

        # Simple beat detection (energy spike in low frequencies)
        bass_energy = np.mean(self.spectrum[:3])
        if bass_energy > 0.7 and (asyncio.get_event_loop().time() - self._last_beat_time) > 0.2:
            self.beat_onset = True
            now = asyncio.get_event_loop().time()
            if self._last_beat_time > 0:
                interval = now - self._last_beat_time
                self._beat_intervals.append(interval)
                self._beat_intervals = self._beat_intervals[-8:]  # Keep last 8
                if len(self._beat_intervals) >= 4:
                    avg_interval = np.median(self._beat_intervals)
                    self.bpm = 60.0 / avg_interval
            self._last_beat_time = now
        else:
            self.beat_onset = False

    def get_input(self) -> 'AudioInput':
        from aurora_web.core.input_context import AudioInput
        return AudioInput(
            bpm=self.bpm,
            beat_onset=self.beat_onset,
            spectrum=self.spectrum,
            volume=float(np.mean(self.spectrum)) if self.spectrum is not None else 0,
            bass=float(np.mean(self.spectrum[:3])) if self.spectrum is not None else 0,
            mids=float(np.mean(self.spectrum[3:10])) if self.spectrum is not None else 0,
            highs=float(np.mean(self.spectrum[10:])) if self.spectrum is not None else 0,
        )

    def stop(self):
        if self._process:
            self._process.terminate()
```

```python
# aurora_web/inputs/video_feed.py
import numpy as np
import cv2
import asyncio
from typing import Optional

class VideoFeed:
    """Captures and analyzes video for motion and light levels"""

    def __init__(self, device: int = 0, width: int = 320, height: int = 240):
        self.device = device
        self.width = width
        self.height = height
        self.frame: Optional[np.ndarray] = None
        self.prev_frame: Optional[np.ndarray] = None
        self.motion_amount: float = 0.0
        self.motion_map: Optional[np.ndarray] = None
        self.light_level: float = 0.5
        self._cap: Optional[cv2.VideoCapture] = None

    async def start(self):
        self._cap = cv2.VideoCapture(self.device)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        asyncio.create_task(self._capture_loop())

    async def _capture_loop(self):
        while self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret:
                self._analyze(frame)
            await asyncio.sleep(0.033)  # ~30fps

    def _analyze(self, frame: np.ndarray):
        # Convert to RGB and store
        self.frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Convert to grayscale for analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Light level (average brightness)
        self.light_level = np.mean(gray) / 255.0

        # Motion detection
        if self.prev_frame is not None:
            diff = cv2.absdiff(gray, self.prev_frame)
            self.motion_map = diff.astype(np.float32) / 255.0
            self.motion_amount = np.mean(self.motion_map)

        self.prev_frame = gray

    def get_input(self) -> 'VideoInput':
        from aurora_web.core.input_context import VideoInput
        return VideoInput(
            frame=self.frame,
            motion_amount=self.motion_amount,
            motion_map=self.motion_map,
            light_level=self.light_level,
        )

    def stop(self):
        if self._cap:
            self._cap.release()
```

```python
# aurora_web/inputs/canvas_feed.py
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import asyncio

@dataclass
class Touch:
    x: float
    y: float
    pressure: float = 1.0
    radius: float = 2.0
    color: tuple[int, int, int] = (255, 255, 255)

class CanvasFeed:
    """Handles touch/paint input from WebSocket"""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.touches: list[Touch] = []
        self.paint_buffer: np.ndarray = np.zeros((height, width, 4), dtype=np.uint8)
        self.last_touch: Optional[Touch] = None
        self._decay_rate: float = 0.0  # 0 = permanent, >0 = fade out

    def touch_start(self, x: float, y: float, color: tuple = (255, 255, 255), radius: float = 2):
        """Handle touch/mouse down"""
        touch = Touch(x=x, y=y, color=color, radius=radius)
        self.touches.append(touch)
        self.last_touch = touch
        self._paint_circle(touch)

    def touch_move(self, x: float, y: float):
        """Handle touch/mouse move"""
        if self.touches:
            touch = self.touches[-1]
            # Draw line from last position
            self._paint_line(touch.x, touch.y, x, y, touch.color, touch.radius)
            touch.x = x
            touch.y = y
            self.last_touch = touch

    def touch_end(self):
        """Handle touch/mouse up"""
        if self.touches:
            self.touches.pop()

    def clear(self):
        """Clear the paint buffer"""
        self.paint_buffer.fill(0)

    def set_decay(self, rate: float):
        """Set paint decay rate (0 = permanent)"""
        self._decay_rate = rate

    def update(self, delta_time: float):
        """Called each frame - apply decay"""
        if self._decay_rate > 0:
            decay = int(self._decay_rate * delta_time * 255)
            alpha = self.paint_buffer[:, :, 3].astype(np.int16)
            alpha = np.clip(alpha - decay, 0, 255).astype(np.uint8)
            self.paint_buffer[:, :, 3] = alpha

    def _paint_circle(self, touch: Touch):
        """Paint a circle at touch location"""
        px = int(touch.x * self.width)
        py = int(touch.y * self.height)
        r = int(touch.radius)

        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx*dx + dy*dy <= r*r:
                    x, y = px + dx, py + dy
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self.paint_buffer[y, x, :3] = touch.color
                        self.paint_buffer[y, x, 3] = 255

    def _paint_line(self, x1, y1, x2, y2, color, radius):
        """Paint a line between two points (Bresenham's)"""
        px1, py1 = int(x1 * self.width), int(y1 * self.height)
        px2, py2 = int(x2 * self.width), int(y2 * self.height)

        steps = max(abs(px2 - px1), abs(py2 - py1), 1)
        for i in range(steps + 1):
            t = i / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            self._paint_circle(Touch(x, y, color=color, radius=radius))

    def get_input(self) -> 'CanvasInput':
        from aurora_web.core.input_context import CanvasInput
        return CanvasInput(
            touches=self.touches.copy(),
            paint_buffer=self.paint_buffer.copy(),
            last_touch=self.last_touch,
        )
```

### 6. Serial Output Process (Separate Process)

```python
# aurora_web/core/serial_process.py
"""
Separate process for serial output to ensure consistent frame rate
without being affected by main process GC or computation delays.
"""
import multiprocessing as mp
import numpy as np
import serial
import time
from typing import Optional

class SharedFrame:
    """Shared memory frame buffer between processes"""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # Shared memory: RGB frame + frame_num + ready flag
        self.frame_size = width * height * 3
        self.shared_array = mp.Array('B', self.frame_size + 8)  # +8 for metadata
        self.lock = mp.Lock()
        self.frame_num = mp.Value('L', 0)  # Unsigned long for frame counter

    def write_frame(self, rgb: np.ndarray, frame_num: int):
        """Write frame from main process"""
        with self.lock:
            # Copy RGB data
            flat = rgb.flatten().astype(np.uint8)
            self.shared_array[:self.frame_size] = flat.tobytes()
            self.frame_num.value = frame_num

    def read_frame(self) -> tuple[np.ndarray, int]:
        """Read frame from serial process"""
        with self.lock:
            data = bytes(self.shared_array[:self.frame_size])
            frame_num = self.frame_num.value
        return np.frombuffer(data, dtype=np.uint8).reshape(self.height, self.width, 3), frame_num


def serial_output_process(
    shared_frame: SharedFrame,
    device: str,
    width: int,
    height: int,
    fps: int,
    gamma: float,
    layout_ltr: bool,
    stop_event: mp.Event
):
    """
    Runs in separate process - reads frames from shared memory and writes to serial.
    Maintains consistent frame rate independent of main process.
    """
    # Build gamma LUT
    gamma_lut = np.array([int(255 * (i / 255) ** gamma) for i in range(256)], dtype=np.uint8)

    # Open serial port
    ser = None
    if device:
        try:
            ser = serial.Serial(device, 115200)
            print(f"[Serial Process] Opened {device}")
        except Exception as e:
            print(f"[Serial Process] Failed to open {device}: {e}")
            return

    frame_time = 1.0 / fps
    last_frame_num = -1

    try:
        while not stop_event.is_set():
            start = time.perf_counter()

            # Read frame from shared memory
            rgb, frame_num = shared_frame.read_frame()

            # Only send if new frame
            if frame_num != last_frame_num:
                last_frame_num = frame_num

                # Apply gamma correction
                rgb = gamma_lut[rgb]

                # Apply snake pattern (alternate rows reversed)
                for y in range(height):
                    should_reverse = (y % 2 == 1) if layout_ltr else (y % 2 == 0)
                    if should_reverse:
                        rgb[y, :, :] = rgb[y, ::-1, :]

                # Flatten, cap at 254, add delimiter
                data = np.clip(rgb.flatten(), 0, 254).astype(np.uint8)

                if ser:
                    ser.write(bytes(data) + b'\xff')

            # Maintain frame rate
            elapsed = time.perf_counter() - start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        if ser:
            ser.close()
            print("[Serial Process] Closed serial port")


class SerialOutputManager:
    """Manages the serial output subprocess"""

    def __init__(self, device: str, width: int, height: int,
                 fps: int = 40, gamma: float = 2.5, layout_ltr: bool = True):
        self.shared_frame = SharedFrame(width, height)
        self.stop_event = mp.Event()
        self.process: Optional[mp.Process] = None

        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.gamma = gamma
        self.layout_ltr = layout_ltr
        self.frame_num = 0

    def start(self):
        """Start the serial output process"""
        self.process = mp.Process(
            target=serial_output_process,
            args=(
                self.shared_frame,
                self.device,
                self.width,
                self.height,
                self.fps,
                self.gamma,
                self.layout_ltr,
                self.stop_event
            ),
            daemon=True
        )
        self.process.start()
        print(f"[Main] Started serial process (PID {self.process.pid})")

    def send_frame(self, rgb: np.ndarray):
        """Send frame to serial process via shared memory"""
        self.frame_num += 1
        self.shared_frame.write_frame(rgb, self.frame_num)

    def stop(self):
        """Stop the serial output process"""
        self.stop_event.set()
        if self.process:
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.terminate()
            print("[Main] Serial process stopped")
```

### 7. Main Pattern Loop (Updated)

```python
# aurora_web/core/pattern_loop.py
import asyncio
import time
from typing import Optional

from aurora_web.core.input_context import InputContext, AudioInput, VideoInput, CanvasInput
from aurora_web.core.serial_process import SerialOutputManager
from aurora_web.inputs.audio_feed import AudioFeed
from aurora_web.inputs.video_feed import VideoFeed
from aurora_web.inputs.canvas_feed import CanvasFeed

class PatternLoop:
    def __init__(
        self,
        drawer_manager,
        serial_manager: SerialOutputManager,
        audio_feed: Optional[AudioFeed] = None,
        video_feed: Optional[VideoFeed] = None,
        canvas_feed: Optional[CanvasFeed] = None,
        fps: int = 40
    ):
        self.drawer_manager = drawer_manager
        self.serial_manager = serial_manager
        self.audio_feed = audio_feed
        self.video_feed = video_feed
        self.canvas_feed = canvas_feed
        self.target_fps = fps
        self.running = False
        self.actual_fps = 0.0
        self._start_time = 0.0
        self._last_frame_time = 0.0
        self._frame_num = 0

    async def run(self):
        self.running = True
        self._start_time = time.perf_counter()
        self._last_frame_time = self._start_time
        frame_time = 1.0 / self.target_fps

        fps_samples = []

        while self.running:
            frame_start = time.perf_counter()

            # Build InputContext
            now = time.perf_counter()
            ctx = InputContext(
                frame_num=self._frame_num,
                time=now - self._start_time,
                delta_time=now - self._last_frame_time,
                audio=self.audio_feed.get_input() if self.audio_feed else AudioInput(),
                video=self.video_feed.get_input() if self.video_feed else VideoInput(),
                canvas=self.canvas_feed.get_input() if self.canvas_feed else CanvasInput(),
            )
            self._last_frame_time = now

            # Update canvas decay
            if self.canvas_feed:
                self.canvas_feed.update(ctx.delta_time)

            # Generate frame
            drawer = self.drawer_manager.active_drawer
            if drawer:
                indices = drawer.draw(ctx)
                rgb = self.drawer_manager.palette.indices_to_rgb(indices)

                # Send to serial process (non-blocking)
                self.serial_manager.send_frame(rgb)

            self._frame_num += 1

            # FPS tracking
            elapsed = time.perf_counter() - frame_start
            fps_samples.append(1.0 / max(elapsed, 0.001))
            if len(fps_samples) > 30:
                fps_samples.pop(0)
            self.actual_fps = sum(fps_samples) / len(fps_samples)

            # Sleep to maintain target FPS
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    def stop(self):
        self.running = False
```

## Configuration (Updated)

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
  change_interval: 30  # seconds, 0 to disable

inputs:
  audio:
    enabled: true
    source: "pulse"  # or "alsa:hw:0" or "file:/path/to/audio"

  video:
    enabled: false
    device: 0
    width: 320
    height: 240

  canvas:
    decay_rate: 0.0  # 0 = permanent paint, >0 = fade out rate

custom_drawers_path: "./custom_drawers"
users_db: "./users.yaml"
```

## WebSocket Protocol (Updated)

```json
// Canvas/paint events (client → server)
{"type": "touch_start", "x": 0.5, "y": 0.3, "color": [255, 0, 0], "radius": 3}
{"type": "touch_move", "x": 0.52, "y": 0.31}
{"type": "touch_end"}
{"type": "clear_canvas"}
{"type": "set_paint_decay", "rate": 0.1}

// Status updates (server → client)
{"type": "status", "drawer": "Bzr", "fps": 39.8, "audio": {"bpm": 120, "beat": false}}
```

## Performance Notes

- **Separate serial process**: Eliminates frame drops from Python GC or main process delays
- **Shared memory**: Zero-copy frame transfer between processes (~0.1ms overhead)
- **NumPy vectorized**: All drawer operations use vectorized numpy (no Python loops)
- **Async I/O**: Audio/video capture runs in background tasks
- **Target**: 40fps stable on Raspberry Pi 4/5

## Migration Path

### Phase 1: Finger Paint Only (MVP)

Standalone Python web server with finger paint - no C++ integration.

**Scope:**
- FastAPI web server with static file serving
- WebSocket for real-time touch input
- CanvasFeed for paint buffer management
- Separate serial process for output
- Simple web UI with canvas + color picker + brush size

**Files to create:**
```
aurora_web/
├── main.py              # FastAPI app entry point
├── core/
│   ├── serial_process.py    # Separate process for serial
│   ├── shared_frame.py      # Shared memory buffer
│   └── palette.py           # Simple gradient palette
├── inputs/
│   └── canvas_feed.py       # Touch/paint handling
├── static/
│   ├── index.html           # Finger paint UI
│   ├── app.js               # WebSocket + canvas logic
│   └── style.css
└── config.yaml
```

**Deliverable:** User can open browser, draw with finger/mouse, see it on LED matrix in real-time.

**No:**
- No pattern drawers
- No audio/video input
- No custom drawer editor
- No user profiles

---

### Phase 2: Basic Pattern Drawers

Port 1-2 simple drawers to Python.

**Scope:**
- Drawer base class with InputContext
- Port AlienBlob (Perlin noise - simplest)
- Drawer selection in web UI
- Settings sliders (auto-generated from schema)

---

### Phase 3: All Drawers + Audio

Port remaining drawers, add audio reactivity.

**Scope:**
- Port Bzr, GrayScott, GinzburgLandau
- AudioFeed with beat detection
- Audio reactivity in drawers

---

### Phase 4: Custom Drawers + Users

Full feature set.

**Scope:**
- Custom drawer YAML format
- Code editor in web UI (CodeMirror)
- User profiles
- Save/load custom drawers
- VideoFeed

---

### Phase 5: Retire C++

Remove C++ pattern generator, single Python codebase.

**Scope:**
- Update systemd service to run Python
- Archive C++ code
- Update documentation
