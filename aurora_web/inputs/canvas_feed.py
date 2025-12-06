"""Canvas/touch input handling for finger paint mode."""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple


@dataclass
class Touch:
    """Represents a touch/paint point."""
    x: float  # 0.0-1.0 normalized x position
    y: float  # 0.0-1.0 normalized y position
    pressure: float = 1.0  # 0.0-1.0 pressure
    radius: float = 2.0  # Brush radius in pixels
    color: Tuple[int, int, int] = (255, 255, 255)  # RGB color


class CanvasFeed:
    """Handles touch/paint input from WebSocket.

    Maintains a paint buffer that accumulates strokes and can
    optionally fade over time.
    """

    def __init__(self, width: int, height: int):
        """Initialize canvas feed.

        Args:
            width: Canvas width in pixels (matches matrix width)
            height: Canvas height in pixels (matches matrix height)
        """
        self.width = width
        self.height = height
        self.touches: List[Touch] = []
        self.paint_buffer: np.ndarray = np.zeros((height, width, 4), dtype=np.uint8)
        self.last_touch: Optional[Touch] = None
        self._decay_rate: float = 0.0  # 0 = permanent, >0 = fade rate per second
        self._current_color: Tuple[int, int, int] = (255, 255, 255)
        self._current_radius: float = 2.0

    def set_color(self, r: int, g: int, b: int) -> None:
        """Set the current paint color."""
        self._current_color = (r, g, b)

    def set_radius(self, radius: float) -> None:
        """Set the current brush radius."""
        self._current_radius = max(1.0, radius)

    def touch_start(
        self,
        x: float,
        y: float,
        color: Optional[Tuple[int, int, int]] = None,
        radius: Optional[float] = None
    ) -> None:
        """Handle touch/mouse down.

        Args:
            x: Normalized x position (0.0-1.0)
            y: Normalized y position (0.0-1.0)
            color: RGB color tuple, or use current color
            radius: Brush radius, or use current radius
        """
        touch = Touch(
            x=x,
            y=y,
            color=color or self._current_color,
            radius=radius or self._current_radius
        )
        self.touches.append(touch)
        self.last_touch = touch
        self._paint_circle(touch)

    def touch_move(self, x: float, y: float) -> None:
        """Handle touch/mouse move.

        Args:
            x: Normalized x position (0.0-1.0)
            y: Normalized y position (0.0-1.0)
        """
        if self.touches:
            touch = self.touches[-1]
            # Draw line from last position
            self._paint_line(touch.x, touch.y, x, y, touch.color, touch.radius)
            touch.x = x
            touch.y = y
            self.last_touch = touch

    def touch_end(self) -> None:
        """Handle touch/mouse up."""
        if self.touches:
            self.touches.pop()

    def clear(self) -> None:
        """Clear the paint buffer."""
        self.paint_buffer.fill(0)

    def set_decay(self, rate: float) -> None:
        """Set paint decay rate.

        Args:
            rate: Decay rate per second (0 = permanent paint)
        """
        self._decay_rate = max(0.0, rate)

    def update(self, delta_time: float) -> None:
        """Update canvas state (apply decay).

        Called each frame by the main loop.

        Args:
            delta_time: Time since last frame in seconds
        """
        if self._decay_rate > 0:
            decay = int(self._decay_rate * delta_time * 255)
            alpha = self.paint_buffer[:, :, 3].astype(np.int16)
            alpha = np.clip(alpha - decay, 0, 255).astype(np.uint8)
            self.paint_buffer[:, :, 3] = alpha

    def _paint_circle(self, touch: Touch) -> None:
        """Paint a filled circle at touch location."""
        px = int(touch.x * self.width)
        py = int(touch.y * self.height)
        r = int(touch.radius)

        # Create coordinate grids for the bounding box
        y_min = max(0, py - r)
        y_max = min(self.height, py + r + 1)
        x_min = max(0, px - r)
        x_max = min(self.width, px + r + 1)

        if y_max <= y_min or x_max <= x_min:
            return

        # Check each pixel in bounding box
        for y in range(y_min, y_max):
            for x in range(x_min, x_max):
                dx = x - px
                dy = y - py
                if dx * dx + dy * dy <= r * r:
                    self.paint_buffer[y, x, :3] = touch.color
                    self.paint_buffer[y, x, 3] = 255

    def _paint_line(
        self,
        x1: float, y1: float,
        x2: float, y2: float,
        color: Tuple[int, int, int],
        radius: float
    ) -> None:
        """Paint a line between two normalized points using circles."""
        px1, py1 = int(x1 * self.width), int(y1 * self.height)
        px2, py2 = int(x2 * self.width), int(y2 * self.height)

        # Number of steps based on distance
        steps = max(abs(px2 - px1), abs(py2 - py1), 1)

        for i in range(steps + 1):
            t = i / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            self._paint_circle(Touch(x, y, color=color, radius=radius))

    def get_rgb_frame(self) -> np.ndarray:
        """Get the paint buffer as an RGB frame.

        Returns:
            RGB array, shape (height, width, 3)
        """
        # Composite paint over black background using alpha
        alpha = self.paint_buffer[:, :, 3:4].astype(np.float32) / 255.0
        rgb = (self.paint_buffer[:, :, :3].astype(np.float32) * alpha).astype(np.uint8)
        return rgb

    def has_paint(self) -> bool:
        """Check if there's any paint on the canvas."""
        return np.any(self.paint_buffer[:, :, 3] > 0)
