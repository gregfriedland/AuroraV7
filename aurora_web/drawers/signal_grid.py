"""SignalGrid drawer — discovered instrument sources (ADR 0005).

Layout on a 32x18 matrix (rows scale with matrix height):

    rows 0-14  five source rows (3 px each): one row per instrument source
               discovered by the online NMF + clustering pipeline. Lowest-
               frequency source on the BOTTOM row. Each row shows a box at
               x = the source's spectral centroid; brightness = its live
               activation, with a flash boost on rising edges. Percussive
               sources naturally flash; sustained sources naturally hold.
    rows 16-17 predictive beat-in-bar boxes (current beat lit, downbeat
               in the brightest palette slot)

Cold start (first ~0.5 s, before the first cluster refresh): dim band bars
are shown across the source rows.
"""

import numpy as np

from aurora_web.drawers.base import Drawer, DrawerContext


class SignalGridDrawer(Drawer):
    """Instrument-source visualization driven by MusicFeatures.sources."""

    # Silence legitimately renders black; exempt from stuck detection
    reacts_to_audio = True

    N_ROWS = 5
    BOX_HALF_W = 2          # box half-width in pixels

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("SignalGrid", width, height, palette_size)
        self.settings = {
            "decay": 50,        # flash decay speed
        }
        self.settings_ranges = {
            "decay": (10, 100),
        }
        self._flash = np.zeros(self.N_ROWS, dtype=np.float32)
        self._beat_flash = 0.0

        h = height
        rows_h = h * 15 // 18
        edges = np.linspace(0, rows_h, self.N_ROWS + 1).astype(int)
        # slot 0 = lowest frequency -> bottom row of the block
        self._row_bounds = [(int(edges[i]), int(edges[i + 1]))
                            for i in range(self.N_ROWS)][::-1]
        self._beat_rows = (h * 16 // 18, h)

    def reset(self) -> None:
        self._flash[:] = 0.0
        self._beat_flash = 0.0

    # Palette color slots: one distinct color per source row
    def _colors(self, ps: int) -> dict:
        return {
            "rows": [ps * 1 // 6, ps * 2 // 6, ps * 3 // 6, ps * 4 // 6, ps * 5 // 6],
            "bar": ps * 3 // 5,
            "downbeat": ps - 1,
            "bands": ps * 2 // 5,
        }

    @staticmethod
    def _scaled(color: int, brightness: float) -> int:
        return max(1, int(color * float(np.clip(brightness, 0.0, 1.0))))

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        indices = np.zeros((ctx.height, ctx.width), dtype=np.int32)
        audio = ctx.audio
        if audio is None:
            return indices
        c = self._colors(ctx.palette_size)
        decay_tau = 0.3 - 0.25 * (self.settings["decay"] / 100.0)  # 0.05-0.3 s
        fade = float(np.exp(-ctx.delta_time / max(decay_tau, 0.01)))

        sources = getattr(audio, "sources", None)
        if sources is not None:
            self._draw_sources(indices, ctx, audio, c, fade)
        else:
            self._draw_fallback_bands(indices, ctx, audio, c)
        self._draw_beat(indices, ctx, audio, c, fade)
        return indices

    def _draw_sources(self, indices, ctx, audio, c, fade):
        sources = audio.sources
        centroids = audio.source_centroid
        active = getattr(audio, "source_active", ())
        n = min(self.N_ROWS, len(sources))
        for i in range(n):
            act = float(sources[i])
            if i < len(active) and active[i]:
                self._flash[i] = 1.0
            self._flash[i] *= fade
            level = max(act, self._flash[i])
            if level < 0.04:
                continue
            r0, r1 = self._row_bounds[i]
            col = int(np.clip(centroids[i], 0.0, 1.0) * (ctx.width - 1))
            x0 = max(0, col - self.BOX_HALF_W)
            x1 = min(ctx.width, col + self.BOX_HALF_W + 1)
            color = c["rows"][i]
            indices[r0:r1, x0:x1] = self._scaled(color, level)
            # soft edges
            if x0 > 0:
                indices[r0:r1, x0 - 1] = self._scaled(color, level * 0.35)
            if x1 < ctx.width:
                indices[r0:r1, x1] = self._scaled(color, level * 0.35)

    def _draw_fallback_bands(self, indices, ctx, audio, c):
        """Cold start: dim band bars until source clusters mature."""
        bands = getattr(audio, "bands", None)
        if bands is None:
            bands = getattr(audio, "spectrum", None)
        if bands is None:
            return
        r1 = self._row_bounds[0][1]  # bottom of the source block
        rows = r1
        nb = len(bands)
        col_w = max(1, ctx.width // nb)
        for i in range(min(nb, ctx.width // col_w)):
            level = float(np.clip(bands[i], 0.0, 1.0))
            filled = int(round(level * rows))
            if filled == 0:
                continue
            x0 = i * col_w
            indices[rows - filled:rows, x0:x0 + col_w] = self._scaled(
                c["bands"], 0.25 + 0.35 * level)

    def _draw_beat(self, indices, ctx, audio, c, fade):
        """Four beat-in-bar boxes; current beat lit, downbeat distinct."""
        r0, r1 = self._beat_rows
        if getattr(audio, "beat_now", False) or getattr(audio, "beat_onset", False):
            self._beat_flash = 1.0
        bpm = getattr(audio, "bpm", None)
        if bpm:
            box_w = max(1, ctx.width // 4)
            beat_in_bar = int(getattr(audio, "beat_in_bar", 1))
            for b in range(4):
                x0 = b * box_w
                x1 = min(ctx.width, x0 + box_w - 1) if b < 3 else ctx.width
                if b + 1 == beat_in_bar:
                    color = c["downbeat"] if b == 0 else c["bar"]
                    indices[r0:r1, x0:x1] = self._scaled(color, max(0.5, self._beat_flash))
                else:
                    indices[r0:r1, x0:x1] = self._scaled(c["bar"], 0.15)
        self._beat_flash *= fade
