"""Audio visualizer drawer — beat circle with onset grid."""

import numpy as np
from aurora_web.drawers.base import Drawer, DrawerContext


class AudioVizDrawer(Drawer):
    """Visualizes audio input on a 32x18 LED matrix.

    Layout:
        Right side:  Circle that flashes on each beat (different color on beat 4)
        Row 16:      Volume bar (horizontal)
        Row 17:      Onset grid (16 positions x 2 cols, brightness = onset strength)
    """

    VOLUME_ROW = 16
    ONSETS_ROW = 17

    # Circle center on right side of display, vertically centered in rows 0-15
    CIRCLE_CX = 23
    CIRCLE_CY = 7
    CIRCLE_RADIUS = 5

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("AudioViz", width, height, palette_size)
        self.settings = {
            "sensitivity": 70,
        }
        self.settings_ranges = {
            "sensitivity": (0, 100),
        }
        self._beat_flash = 0.0  # decaying flash intensity
        self._smoothed_volume = 0.0
        self._smoothed_onset_grid = np.zeros(16, dtype=np.float32)
        self._smooth_factor = 0.15

        # Precompute circle mask
        self._circle_pixels = []
        for y in range(height):
            for x in range(width):
                dx = x - self.CIRCLE_CX
                dy = y - self.CIRCLE_CY
                if dx * dx + dy * dy <= self.CIRCLE_RADIUS * self.CIRCLE_RADIUS:
                    self._circle_pixels.append((y, x))

    def reset(self) -> None:
        self._beat_flash = 0.0
        self._smoothed_volume = 0.0
        self._smoothed_onset_grid[:] = 0

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        indices = np.zeros((ctx.height, ctx.width), dtype=np.int32)
        audio = ctx.audio

        if audio is None or audio.spectrum is None:
            return indices

        ps = ctx.palette_size

        # Trigger flash on beat onset
        if audio.beat_onset:
            self._beat_flash = 1.0

        # Smooth volume, boosted by sensitivity (real-music RMS is ~0.02-0.3)
        gain = 1.0 + self.settings["sensitivity"] / 10.0
        level = min(1.0, audio.volume * gain)
        a = self._smooth_factor
        self._smoothed_volume += a * (level - self._smoothed_volume)

        self._draw_beat_circle(indices, ctx, audio, ps)
        self._draw_volume(indices, ctx, audio, ps * 3 // 5)
        self._draw_onsets(indices, ctx, ps * 4 // 5)

        # Decay flash after drawing
        self._beat_flash *= 0.82

        return indices

    # ------------------------------------------------------------------
    # Beat circle (right side, rows 0-15)
    # ------------------------------------------------------------------
    def _draw_beat_circle(self, indices, ctx, audio, ps):
        if self._beat_flash < 0.02:
            return

        color = ps * 1 // 5

        brightness = self._beat_flash
        c = max(1, int(color * brightness))

        for y, x in self._circle_pixels:
            if 0 <= y < ctx.height and 0 <= x < ctx.width:
                indices[y, x] = c

    # ------------------------------------------------------------------
    # Volume bar  (row 16)
    # ------------------------------------------------------------------
    def _draw_volume(self, indices, ctx, audio, color):
        if self.VOLUME_ROW >= ctx.height:
            return
        fill = int(self._smoothed_volume * ctx.width)
        fill = min(fill, ctx.width)
        indices[self.VOLUME_ROW, :fill] = color

    # ------------------------------------------------------------------
    # Onset grid  (row 17, 16 positions x 2 cols)
    # Driven by the external 16th-note beat feed (ctx.beat_onsets).
    # ------------------------------------------------------------------
    def _draw_onsets(self, indices, ctx, color):
        if self.ONSETS_ROW >= ctx.height:
            return

        if ctx.beat_onsets:
            grid = np.zeros(16, dtype=np.float32)
            n = min(16, len(ctx.beat_onsets))
            grid[:n] = [1.0 if onset else 0.0 for onset in ctx.beat_onsets[:n]]
            self._smoothed_onset_grid = np.maximum(
                grid, self._smoothed_onset_grid * 0.9
            )
        else:
            self._smoothed_onset_grid *= 0.9

        for i in range(16):
            val = self._smoothed_onset_grid[i]
            if val < 0.01:
                continue
            brightness = min(1.0, val)
            col_start = i * 2
            c = max(1, int(color * brightness))
            if col_start < ctx.width:
                indices[self.ONSETS_ROW, col_start] = c
            if col_start + 1 < ctx.width:
                indices[self.ONSETS_ROW, col_start + 1] = c
