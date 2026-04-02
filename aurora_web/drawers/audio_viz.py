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

    def reset(self) -> None:
        pass

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        indices = np.zeros((ctx.height, ctx.width), dtype=np.int32)
        audio = ctx.audio

        if audio is None or not audio.is_active or audio.spectrum is None:
            return indices

        sens = self.settings["sensitivity"] / 50.0  # 0->0, 50->1, 100->2
        ps = ctx.palette_size

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

        for i in range(num_bars):
            bar_h = int(audio.spectrum[i] * sens * max_h)
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
        fill_cols = int(audio.beat_phase * ctx.width)

        if audio.beat_onset:
            for r in range(self.BEAT_ROWS):
                y = self.SPECTRUM_ROWS + r
                if y < ctx.height:
                    indices[y, :] = color
        else:
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
        fill = int(audio.volume * ctx.width)
        fill = min(fill, ctx.width)
        indices[self.VOLUME_ROW, :fill] = color

    # ------------------------------------------------------------------
    # Bass / Mids / Highs  (row 17)
    # ------------------------------------------------------------------
    def _draw_bands(self, indices, ctx, audio, color):
        if self.BANDS_ROW >= ctx.height:
            return

        regions = [
            (0, 10, audio.bass),
            (11, 21, audio.mids),
            (22, 32, audio.highs),
        ]
        for start, end, level in regions:
            end = min(end, ctx.width)
            span = end - start
            fill = int(level * span)
            fill = min(fill, span)
            indices[self.BANDS_ROW, start:start + fill] = color
