"""Base drawer class for pattern generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np


@dataclass
class DrawerContext:
    """Context passed to drawers each frame."""
    width: int
    height: int
    frame_num: int
    time: float
    delta_time: float
    palette_size: int = 4096


class Drawer(ABC):
    """Abstract base class for pattern drawers.

    Drawers generate frames by returning palette indices that are
    then mapped to RGB colors via a Palette.
    """

    def __init__(self, name: str, width: int, height: int, palette_size: int = 4096):
        """Initialize drawer.

        Args:
            name: Display name for this drawer
            width: Matrix width in pixels
            height: Matrix height in pixels
            palette_size: Number of colors in palette
        """
        self.name = name
        self.width = width
        self.height = height
        self.palette_size = palette_size
        self.settings: Dict[str, int] = {}
        self.settings_ranges: Dict[str, Tuple[int, int]] = {}
        self.frame = 0

    @abstractmethod
    def reset(self) -> None:
        """Reset drawer state to initial conditions."""
        pass

    @abstractmethod
    def draw(self, ctx: DrawerContext) -> np.ndarray:
        """Draw a frame.

        Args:
            ctx: DrawerContext with frame timing and dimensions

        Returns:
            numpy array of shape (height, width) with palette indices
        """
        pass

    def update_settings(self, settings: Dict[str, int]) -> None:
        """Update drawer settings, clamping to valid ranges.

        Args:
            settings: Dict of setting name to value
        """
        for key, value in settings.items():
            if key in self.settings_ranges:
                min_val, max_val = self.settings_ranges[key]
                self.settings[key] = max(min_val, min(max_val, int(value)))
            elif key in self.settings:
                self.settings[key] = int(value)

    def randomize_settings(self) -> None:
        """Randomize all settings within their valid ranges."""
        for key, (min_val, max_val) in self.settings_ranges.items():
            self.settings[key] = np.random.randint(min_val, max_val + 1)
        self.reset()

    def get_settings_info(self) -> Dict:
        """Get settings with their current values and ranges.

        Returns:
            Dict with setting info for UI rendering
        """
        return {
            key: {
                "value": self.settings[key],
                "min": self.settings_ranges.get(key, (0, 100))[0],
                "max": self.settings_ranges.get(key, (0, 100))[1],
            }
            for key in self.settings
        }
