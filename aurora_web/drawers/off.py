"""Simple scrolling color ramp drawer for testing."""

import numpy as np
from aurora_web.drawers.base import Drawer, DrawerContext


class OffDrawer(Drawer):
    """Simple scrolling color ramp pattern.

    Creates a horizontal color gradient that scrolls across the display.
    Useful for testing the drawer system.
    """

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("Off", width, height, palette_size)

        # Settings
        self.settings = {
            "speed": 5,
        }
        self.settings_ranges = {
            "speed": (1, 20),
        }

        self.pos = 0.0
        self.reset()

    def reset(self) -> None:
        """Reset position to start."""
        self.pos = 0.0

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        """Draw scrolling color ramp.

        Returns:
            Array of palette indices, shape (height, width)
        """
        # Create x coordinate array
        x = np.arange(self.width)

        # Add position offset and wrap
        x_offset = (x + int(self.pos)) % self.width

        # Map x position to palette index (0 to palette_size-1)
        indices = (x_offset * (self.palette_size - 1) // (self.width - 1)).astype(np.int32)

        # Broadcast to full height
        frame = np.tile(indices, (self.height, 1))

        # Update position for next frame
        self.pos += self.settings["speed"] * ctx.delta_time * 10

        return frame
