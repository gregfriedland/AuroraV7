"""Drawer manager for mode switching and drawer orchestration."""

import time
import numpy as np

from aurora_web.core.palette import Palette
from aurora_web.drawers.base import Drawer, DrawerContext


class DrawerManager:
    """Manages pattern drawers and mode switching.

    Handles switching between paint mode (browser-sourced frames) and
    pattern mode (server-generated frames from drawers).
    """

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        """Initialize drawer manager.

        Args:
            width: Matrix width
            height: Matrix height
            palette_size: Size of color palette
        """
        self.width = width
        self.height = height
        self.palette_size = palette_size

        # Drawer registry
        self.drawers: dict[str, Drawer] = {}
        self.active_drawer: Drawer | None = None

        # Mode: "paint" or "pattern"
        self.mode = "paint"

        # Color palette for pattern mode
        self.palette = Palette(size=palette_size)

        # Timing
        self.frame_num = 0
        self.start_time = time.time()
        self.last_time = self.start_time

        # Default black frame
        self.black_frame = np.zeros((height, width, 3), dtype=np.uint8)

    def register_drawer(self, drawer: Drawer) -> None:
        """Register a drawer.

        Args:
            drawer: Drawer instance to register
        """
        self.drawers[drawer.name] = drawer

    def get_drawer_list(self) -> list[dict]:
        """Get list of available drawers with their info.

        Returns:
            List of drawer info dicts
        """
        return [
            {
                "name": name,
                "settings": drawer.get_settings_info()
            }
            for name, drawer in self.drawers.items()
        ]

    def set_mode(self, mode: str) -> bool:
        """Set current mode.

        Args:
            mode: "paint" or "pattern"

        Returns:
            True if mode was changed
        """
        if mode in ("paint", "pattern"):
            self.mode = mode
            return True
        return False

    def set_active_drawer(self, name: str) -> bool:
        """Set the active drawer by name.

        Args:
            name: Drawer name

        Returns:
            True if drawer was found and set
        """
        if name in self.drawers:
            self.active_drawer = self.drawers[name]
            self.active_drawer.reset()
            return True
        return False

    def update_drawer_settings(self, settings: dict[str, int]) -> bool:
        """Update settings on active drawer.

        Args:
            settings: Dict of setting name to value

        Returns:
            True if settings were updated
        """
        if self.active_drawer:
            self.active_drawer.update_settings(settings)
            return True
        return False

    def set_palette_colors(self, base_colors: list[tuple]) -> None:
        """Update palette with new base colors.

        Args:
            base_colors: List of (R, G, B) tuples
        """
        self.palette.set_base_colors(base_colors)

    def get_frame(self, browser_frame: np.ndarray | None = None) -> np.ndarray:
        """Get current frame based on mode.

        Args:
            browser_frame: Frame from browser (used in paint mode)

        Returns:
            RGB frame array, shape (height, width, 3)
        """
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        self.frame_num += 1

        if self.mode == "paint":
            # Use browser frame or black
            return browser_frame if browser_frame is not None else self.black_frame

        elif self.mode == "pattern" and self.active_drawer:
            # Generate frame from drawer
            ctx = DrawerContext(
                width=self.width,
                height=self.height,
                frame_num=self.frame_num,
                time=current_time - self.start_time,
                delta_time=delta_time,
                palette_size=self.palette_size
            )

            # Get palette indices from drawer
            indices = self.active_drawer.draw(ctx)

            # Convert to RGB
            return self.palette.indices_to_rgb(indices)

        else:
            return self.black_frame

    def get_status(self) -> dict:
        """Get current status for UI.

        Returns:
            Status dict
        """
        return {
            "mode": self.mode,
            "active_drawer": self.active_drawer.name if self.active_drawer else None,
            "drawers": list(self.drawers.keys()),
        }
