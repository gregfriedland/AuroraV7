"""Camera drawer - converts video feed to LED matrix palette indices."""

import numpy as np
from aurora_web.drawers.base import Drawer, DrawerContext


class CameraDrawer(Drawer):
    """Displays camera feed mapped to the color palette.

    Converts camera frames to grayscale luminance, then maps
    brightness values to palette indices. Supports edge-detection
    and motion-map display modes.
    """

    # Display modes
    MODE_LUMINANCE = 1
    MODE_EDGES = 2
    MODE_MOTION = 3

    def __init__(self, width: int, height: int, palette_size: int = 4096,
                 video_feed=None):
        """Initialize camera drawer.

        Args:
            width: Matrix width in pixels
            height: Matrix height in pixels
            palette_size: Number of colors in palette
            video_feed: VideoFeed or MockVideoFeed instance
        """
        super().__init__("Camera", width, height, palette_size)
        self.video_feed = video_feed

        # Settings
        self.settings = {
            "mode": self.MODE_LUMINANCE,
            "brightness": 50,
            "contrast": 50,
            "mirror": 1,
        }
        self.settings_ranges = {
            "mode": (1, 3),
            "brightness": (0, 100),
            "contrast": (0, 100),
            "mirror": (0, 1),
        }

        self.reset()

    def reset(self) -> None:
        """Reset drawer state."""
        self._prev_frame = None

    def set_video_feed(self, video_feed) -> None:
        """Set or replace the video feed source."""
        self.video_feed = video_feed

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        """Draw camera frame mapped to palette indices.

        Returns:
            Array of palette indices, shape (height, width)
        """
        if self.video_feed is None:
            return self._fallback_pattern(ctx)

        video_input = self.video_feed.get_input()

        if video_input.frame is None:
            return self._fallback_pattern(ctx)

        mode = self.settings["mode"]

        if mode == self.MODE_EDGES:
            normalized = self._compute_edges(video_input.frame)
        elif mode == self.MODE_MOTION and video_input.motion_map is not None:
            normalized = self._resize(video_input.motion_map)
        else:
            normalized = self._frame_to_luminance(video_input.frame)

        # Apply brightness/contrast
        normalized = self._adjust_brightness_contrast(normalized)

        # Mirror horizontally (selfie-style) if enabled
        if self.settings["mirror"]:
            normalized = np.fliplr(normalized)

        # Map 0.0-1.0 to palette indices
        indices = (normalized * (self.palette_size - 1)).astype(np.int32)
        return np.clip(indices, 0, self.palette_size - 1)

    def _frame_to_luminance(self, frame: np.ndarray) -> np.ndarray:
        """Convert RGB frame to luminance and resize to matrix dimensions.

        Returns:
            Normalized float array (0.0-1.0), shape (height, width)
        """
        # Resize first, then convert (more efficient for small targets)
        resized = self._resize_rgb(frame)
        # ITU-R BT.709 luminance
        luminance = (0.2126 * resized[:, :, 0] +
                     0.7152 * resized[:, :, 1] +
                     0.0722 * resized[:, :, 2])
        return luminance / 255.0

    def _compute_edges(self, frame: np.ndarray) -> np.ndarray:
        """Compute edge-detection on frame using Sobel-like kernels.

        Returns:
            Normalized float array (0.0-1.0), shape (height, width)
        """
        luminance = self._frame_to_luminance(frame)

        # Simple Sobel edge detection without OpenCV dependency
        # Horizontal kernel
        gx = np.zeros_like(luminance)
        gx[:, 1:-1] = luminance[:, 2:] - luminance[:, :-2]
        # Vertical kernel
        gy = np.zeros_like(luminance)
        gy[1:-1, :] = luminance[2:, :] - luminance[:-2, :]

        edges = np.sqrt(gx**2 + gy**2)
        # Normalize to 0-1
        max_val = edges.max()
        if max_val > 0:
            edges = edges / max_val
        return edges

    def _resize(self, arr: np.ndarray) -> np.ndarray:
        """Resize a 2D float array to matrix dimensions using nearest-neighbor.

        Args:
            arr: Input 2D array

        Returns:
            Resized array, shape (self.height, self.width)
        """
        src_h, src_w = arr.shape[:2]
        row_idx = (np.arange(self.height) * src_h // self.height).astype(int)
        col_idx = (np.arange(self.width) * src_w // self.width).astype(int)
        return arr[np.ix_(row_idx, col_idx)]

    def _resize_rgb(self, frame: np.ndarray) -> np.ndarray:
        """Resize an RGB frame to matrix dimensions using nearest-neighbor.

        Args:
            frame: RGB frame (h, w, 3)

        Returns:
            Resized frame, shape (self.height, self.width, 3)
        """
        src_h, src_w = frame.shape[:2]
        row_idx = (np.arange(self.height) * src_h // self.height).astype(int)
        col_idx = (np.arange(self.width) * src_w // self.width).astype(int)
        return frame[np.ix_(row_idx, col_idx)]

    def _adjust_brightness_contrast(self, arr: np.ndarray) -> np.ndarray:
        """Apply brightness and contrast adjustment.

        Args:
            arr: Normalized float array (0.0-1.0)

        Returns:
            Adjusted array, clipped to 0.0-1.0
        """
        # brightness: 0=dark, 50=neutral, 100=bright
        brightness_offset = (self.settings["brightness"] - 50) / 100.0

        # contrast: 0=flat, 50=neutral, 100=high
        contrast_factor = self.settings["contrast"] / 50.0

        result = (arr - 0.5) * contrast_factor + 0.5 + brightness_offset
        return np.clip(result, 0.0, 1.0)

    def _fallback_pattern(self, ctx: DrawerContext) -> np.ndarray:
        """Generate a fallback pattern when no video feed is available.

        Shows a slow pulsing gradient to indicate "waiting for camera".
        """
        x = np.arange(self.width)
        pulse = (np.sin(ctx.time * 2.0) + 1.0) / 2.0
        indices = ((x / max(self.width - 1, 1)) * pulse * (self.palette_size - 1)).astype(np.int32)
        return np.tile(indices, (self.height, 1))
