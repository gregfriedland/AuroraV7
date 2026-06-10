"""BeatBouncer drawer driven by V6-style external onset data."""

import numpy as np

from aurora_web.drawers.base import Drawer, DrawerContext


class BeatBouncerDrawer(Drawer):
    """Draw vertical onset bands from an external beat detector."""

    # Silence legitimately renders black; exempt from stuck detection
    reacts_to_audio = True

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("BeatBouncer", width, height, palette_size)
        self.settings = {
            "bandHeight": 20,
            "color": 50,
        }
        self.settings_ranges = {
            "bandHeight": (1, height),
            "color": (1, 100),
        }

    def reset(self) -> None:
        """BeatBouncer has no persistent animation state."""

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        """Map active onset buckets to horizontal palette bands."""
        indices = np.zeros((self.height, self.width), dtype=np.int32)
        onsets = ctx.beat_onsets
        if not onsets:
            return indices

        band_height = min(self.height, max(1, self.settings["bandHeight"]))
        y_start = max(0, self.height // 2 - band_height // 2)
        y_end = min(self.height, y_start + band_height)
        color_index = int(self.settings["color"] * self.palette_size / 100)

        onset_count = len(onsets)
        for onset_index, active in enumerate(onsets):
            if not active:
                continue
            x_start = onset_index * self.width // onset_count
            x_end = (onset_index + 1) * self.width // onset_count
            indices[y_start:y_end, x_start:x_end] = color_index

        return indices
