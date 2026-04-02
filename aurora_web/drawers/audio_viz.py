"""Audio visualizer drawer — spectrum bars, beat phase, volume, and frequency bands."""

import numpy as np
from aurora_web.drawers.base import Drawer, DrawerContext


class AudioVizDrawer(Drawer):
    """Visualizes audio input on a 32x18 LED matrix.

    Layout:
        Rows 0-13:  16 spectrum bars (2 cols each, bottom-up fill)
        Rows 14-15: Beat phase sweep (left-right, flashes on beat_onset)
        Row 16:     Volume bar (horizontal)
        Row 17:     Bass | Mids | Highs (3 separate bars)
    """

    SPECTRUM_ROWS = 14   # rows 0-13
    BEAT_ROWS = 2        # rows 14-15
    VOLUME_ROW = 16
    BANDS_ROW = 17

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("AudioViz", width, height, palette_size)
        self.settings = {
            "sensitivity": 70,
        }
        self.settings_ranges = {
            "sensitivity": (0, 100),
        }
        self._smoothed_spectrum = np.zeros(16, dtype=np.float32)
        self._beat_brightness = 0.0
        self._smoothed_volume = 0.0
        self._smoothed_bass = 0.0
        self._smoothed_mids = 0.0
        self._smoothed_highs = 0.0
        self._smooth_factor = 0.15  # 0=frozen, 1=instant

    def reset(self) -> None:
        self._smoothed_spectrum[:] = 0
        self._beat_brightness = 0.0
        self._smoothed_volume = 0.0
        self._smoothed_bass = 0.0
        self._smoothed_mids = 0.0
        self._smoothed_highs = 0.0

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        indices = np.zeros((ctx.height, ctx.width), dtype=np.int32)
        audio = ctx.audio

        if audio is None or not audio.is_active or audio.spectrum is None:
            return indices

        sens = self.settings["sensitivity"] / 50.0  # 0->0, 50->1, 100->2
        ps = ctx.palette_size
        a = self._smooth_factor

        # Smooth beat: jump to 1.0 on onset, decay otherwise
        if audio.beat_onset:
            self._beat_brightness = 1.0
        else:
            self._beat_brightness *= 0.85  # decay per frame

        # Smooth volume and bands
        self._smoothed_volume += a * (audio.volume - self._smoothed_volume)
        self._smoothed_bass += a * (audio.bass - self._smoothed_bass)
        self._smoothed_mids += a * (audio.mids - self._smoothed_mids)
        self._smoothed_highs += a * (audio.highs - self._smoothed_highs)

        self._draw_spectrum(indices, ctx, audio, sens, ps * 1 // 5)
        self._draw_beat_phase(indices, ctx, audio, ps * 2 // 5)
        self._draw_volume(indices, ctx, audio, ps * 3 // 5)
        self._draw_bands(indices, ctx, audio, ps * 4 // 5)

        return indices

    # ------------------------------------------------------------------
    # Spectrum bars  (rows 0-13, 16 bars x 2 cols)
    # ------------------------------------------------------------------
    def _draw_spectrum(self, indices, ctx, audio, sens, color):
        num_bars = min(16, len(audio.spectrum))
        max_h = self.SPECTRUM_ROWS

        # Exponential moving average for smooth bars
        a = self._smooth_factor
        self._smoothed_spectrum[:num_bars] = (
            a * audio.spectrum[:num_bars]
            + (1 - a) * self._smoothed_spectrum[:num_bars]
        )

        for i in range(num_bars):
            bar_h = int(self._smoothed_spectrum[i] * sens * max_h)
            bar_h = min(bar_h, max_h)

            col_start = i * 2
            for row in range(bar_h):
                y = max_h - 1 - row
                if col_start < ctx.width:
                    indices[y, col_start] = color
                if col_start + 1 < ctx.width:
                    indices[y, col_start + 1] = color

    # ------------------------------------------------------------------
    # Beat phase sweep  (rows 14-15)
    # ------------------------------------------------------------------
    def _draw_beat_phase(self, indices, ctx, audio, color):
        # Fill width based on beat brightness (EMA decay after onset)
        fill_cols = int(self._beat_brightness * ctx.width)
        for r in range(self.BEAT_ROWS):
            y = self.SPECTRUM_ROWS + r
            if y < ctx.height:
                indices[y, :fill_cols] = color

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
    # Bass / Mids / Highs  (row 17)
    # ------------------------------------------------------------------
    def _draw_bands(self, indices, ctx, audio, color):
        if self.BANDS_ROW >= ctx.height:
            return

        regions = [
            (0, 10, self._smoothed_bass),
            (11, 21, self._smoothed_mids),
            (22, 32, self._smoothed_highs),
        ]
        for start, end, level in regions:
            end = min(end, ctx.width)
            span = end - start
            fill = int(level * span)
            fill = min(fill, span)
            indices[self.BANDS_ROW, start:start + fill] = color
