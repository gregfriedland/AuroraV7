"""Video drawer - maps camera input to palette-colored pixels."""

import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor

from aurora_web.drawers.base import Drawer, DrawerContext


class VideoDrawer(Drawer):
    """Captures from the Pi camera and maps grayscale intensity to palette indices.

    The camera frame is downscaled to the panel resolution, converted to
    grayscale, and the brightness of each pixel is mapped to a palette index.
    A colorSpeed setting cycles the palette offset over time.
    """

    def __init__(self, width: int, height: int, palette_size: int = 4096,
                 device: int = 0):
        super().__init__("Video", width, height, palette_size)

        self.device = device

        # Settings
        self.settings = {
            "colorSpeed": 0,
            "brightness": 50,
            "contrast": 50,
        }
        self.settings_ranges = {
            "colorSpeed": (0, 50),
            "brightness": (0, 100),
            "contrast": (0, 100),
        }

        # Animation state
        self.color_index = 0

        # Camera state
        self._cap: cv2.VideoCapture | None = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._last_frame: np.ndarray | None = None

    def _ensure_camera(self) -> bool:
        """Open camera if not already open.

        Returns:
            True if camera is available
        """
        if self._cap is not None and self._cap.isOpened():
            return True

        try:
            self._cap = cv2.VideoCapture(self.device)
            if self._cap.isOpened():
                # Use low resolution since we'll downscale anyway
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                self._cap.set(cv2.CAP_PROP_FPS, 15)
                print(f"[VideoDrawer] Camera opened (device {self.device})")
                return True
            else:
                self._cap = None
                return False
        except Exception as e:
            print(f"[VideoDrawer] Failed to open camera: {e}")
            self._cap = None
            return False

    def _release_camera(self) -> None:
        """Release camera resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            print("[VideoDrawer] Camera released")

    def reset(self) -> None:
        """Reset drawer state."""
        self.color_index = 0
        self._last_frame = None

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        """Capture frame, convert to grayscale, map to palette indices.

        Returns:
            Array of palette indices, shape (height, width)
        """
        color_speed = self.settings["colorSpeed"]
        brightness = self.settings["brightness"]
        contrast = self.settings["contrast"]

        # Try to grab a frame
        gray = None
        if self._ensure_camera():
            ret, frame = self._cap.read()
            if ret and frame is not None:
                # Downscale to panel resolution
                small = cv2.resize(frame, (self.width, self.height),
                                   interpolation=cv2.INTER_AREA)
                # Convert to grayscale
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
                self._last_frame = gray

        # Fall back to last frame or black
        if gray is None:
            gray = self._last_frame if self._last_frame is not None else \
                np.zeros((self.height, self.width), dtype=np.float32)

        # Apply brightness and contrast adjustments
        # brightness: 0=dark, 50=neutral, 100=bright
        # contrast: 0=flat, 50=neutral, 100=high
        brightness_offset = (brightness - 50) * 2.55  # -127.5 to +127.5
        contrast_factor = 1.0 + (contrast - 50) * 0.04  # 0.0 to 3.0

        gray = (gray - 128.0) * contrast_factor + 128.0 + brightness_offset
        gray = np.clip(gray, 0, 255)

        # Map grayscale [0, 255] to palette indices [0, palette_size)
        indices = (gray / 255.0 * (self.palette_size - 1)).astype(np.int32)

        # Apply color offset
        indices = (indices + self.color_index) % self.palette_size

        # Update color cycling
        self.color_index = (self.color_index + color_speed) % self.palette_size

        return indices

    def __del__(self):
        """Clean up camera on deletion."""
        self._release_camera()
