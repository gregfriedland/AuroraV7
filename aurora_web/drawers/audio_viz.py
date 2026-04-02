"""Audio visualizer drawer — spectrum bars, beat phase, volume, and frequency bands."""

import numpy as np
from aurora_web.drawers.base import Drawer, DrawerContext


class AudioVizDrawer(Drawer):
    """Visualizes audio input on a 32×18 LED matrix.

    Layout:
        Rows 0-13:  16 spectrum bars (2 cols each, bottom-up fill)
        Rows 14-15: Beat phase sweep (left→right, flashes on beat_onset)
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
            "colorSpeed": 10,
        }
        self.settings_ranges = {
            "sensitivity": (0, 100),
            "colorSpeed": (0, 50),
        }
        self._phase_offset = 0.0

    def reset(self) -> None:
        self._phase_offset = 0.0

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        indices = np.zeros((ctx.height, ctx.width), dtype=np.int32)
        audio = ctx.audio

        # Animate palette offset
        speed = self.settings["colorSpeed"]
        self._phase_offset += ctx.delta_time * speed * 40
        offset = int(self._phase_offset) % ctx.palette_size

        if audio is None or not audio.is_active or audio.spectrum is None:
            self._draw_waiting(indices, ctx, offset)
            return indices

        sens = self.settings["sensitivity"] / 50.0  # 0→0, 50→1, 100→2

        self._draw_spectrum(indices, ctx, audio, sens, offset)
        self._draw_beat_phase(indices, ctx, audio, offset)
        self._draw_volume(indices, ctx, audio, offset)
        self._draw_bands(indices, ctx, audio, offset)

        return indices

    # ------------------------------------------------------------------
    # Waiting / fallback pattern
    # ------------------------------------------------------------------
    def _draw_waiting(
        self, indices: np.ndarray, ctx: DrawerContext, offset: int
    ) -> None:
        """Dim scrolling bars when no audio is connected."""
        for x in range(ctx.width):
            val = int((x + offset * 0.1) * ctx.palette_size / ctx.width) % ctx.palette_size
            # Dim it — use lower quarter of palette
            val = val // 4
            for y in range(ctx.height):
                if (x + y) % 4 == int(ctx.time * 2) % 4:
                    indices[y, x] = val

    # ------------------------------------------------------------------
    # Spectrum bars  (rows 0-13, 16 bars × 2 cols)
    # ------------------------------------------------------------------
    def _draw_spectrum(
        self,
        indices: np.ndarray,
        ctx: DrawerContext,
        audio,
        sens: float,
        offset: int,
    ) -> None:
        num_bars = min(16, len(audio.spectrum))
        max_h = self.SPECTRUM_ROWS  # 14

        for i in range(num_bars):
            bar_h = int(audio.spectrum[i] * sens * max_h)
            bar_h = min(bar_h, max_h)

            # Color: spread bars across palette for rainbow
            color = (offset + i * ctx.palette_size // num_bars) % ctx.palette_size

            col_start = i * 2
            for row in range(bar_h):
                y = max_h - 1 - row  # fill bottom-up
                if col_start < ctx.width:
                    indices[y, col_start] = color
                if col_start + 1 < ctx.width:
                    indices[y, col_start + 1] = color

    # ------------------------------------------------------------------
    # Beat phase sweep  (rows 14-15)
    # ------------------------------------------------------------------
    def _draw_beat_phase(
        self,
        indices: np.ndarray,
        ctx: DrawerContext,
        audio,
        offset: int,
    ) -> None:
        fill_cols = int(audio.beat_phase * ctx.width)
        color = (offset + ctx.palette_size // 2) % ctx.palette_size

        if audio.beat_onset:
            # Flash entire 2 rows to bright color on beat
            bright = (offset + ctx.palette_size * 3 // 4) % ctx.palette_size
            for r in range(self.BEAT_ROWS):
                y = self.SPECTRUM_ROWS + r
                if y < ctx.height:
                    indices[y, :] = bright
        else:
            for r in range(self.BEAT_ROWS):
                y = self.SPECTRUM_ROWS + r
                if y < ctx.height:
                    indices[y, :fill_cols] = color

    # ------------------------------------------------------------------
    # Volume bar  (row 16)
    # ------------------------------------------------------------------
    def _draw_volume(
        self,
        indices: np.ndarray,
        ctx: DrawerContext,
        audio,
        offset: int,
    ) -> None:
        if self.VOLUME_ROW >= ctx.height:
            return
        fill = int(audio.volume * ctx.width)
        fill = min(fill, ctx.width)
        color = (offset + ctx.palette_size // 3) % ctx.palette_size
        indices[self.VOLUME_ROW, :fill] = color

    # ------------------------------------------------------------------
    # Bass / Mids / Highs  (row 17)
    # ------------------------------------------------------------------
    def _draw_bands(
        self,
        indices: np.ndarray,
        ctx: DrawerContext,
        audio,
        offset: int,
    ) -> None:
        if self.BANDS_ROW >= ctx.height:
            return

        # Three regions: cols 0-9, 11-20, 22-31
        regions = [
            (0, 10, audio.bass),
            (11, 21, audio.mids),
            (22, 32, audio.highs),
        ]
        for idx, (start, end, level) in enumerate(regions):
            end = min(end, ctx.width)
            span = end - start
            fill = int(level * span)
            fill = min(fill, span)
            color = (offset + idx * ctx.palette_size // 3) % ctx.palette_size
            indices[self.BANDS_ROW, start:start + fill] = color
