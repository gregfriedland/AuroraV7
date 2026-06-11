"""SignalGrid drawer — discovered instrument sources (ADR 0005).

Renders RGB directly (returns_rgb) instead of palette indices: every source
row has ONE fixed hue, and brightness scales that color's value. Scaling
palette indices (the index-drawer idiom) slides along the palette gradient,
so "dimmer" meant "different color" — no stable visual identity per source.

Layout on a 32x18 matrix (rows scale with matrix height):

    rows 0-14  five source rows (3 px each), lowest-frequency source on the
               BOTTOM row. Each row: a crisp fixed-width box at x = the
               source's spectral centroid whose brightness follows the
               source's live activation — a hit is always the same box, same
               place, same color, flashing bright and decaying.
    rows 16-17 beat-in-bar boxes (current beat white, downbeat gold)
"""

import numpy as np

from aurora_web.drawers.base import Drawer, DrawerContext


class SignalGridDrawer(Drawer):
    """Instrument-source visualization driven by MusicFeatures.sources."""

    # Silence legitimately renders black; exempt from stuck detection
    reacts_to_audio = True
    # Draw RGB directly; DrawerManager skips palette conversion
    returns_rgb = True

    N_ROWS = 5
    BOX_W = 6               # box width in pixels (crisp, no soft edges)

    # one fixed color per source row (top -> bottom)
    ROW_COLORS = np.array([
        [180, 60, 255],     # violet  (highest frequency)
        [40, 120, 255],     # blue
        [0, 220, 130],      # green
        [255, 180, 0],      # amber
        [255, 60, 60],      # red     (lowest frequency)
    ], dtype=np.float32)

    BAR_DIM = np.array([60, 60, 70], dtype=np.float32)
    BAR_LIT = np.array([240, 240, 255], dtype=np.float32)
    BAR_DOWN = np.array([255, 200, 40], dtype=np.float32)

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("SignalGrid", width, height, palette_size)
        self.settings = {
            "decay": 50,        # release speed of the box brightness
        }
        self.settings_ranges = {
            "decay": (10, 100),
        }
        self._level = np.zeros(self.N_ROWS, dtype=np.float32)
        self._beat_flash = 0.0

        h = height
        rows_h = h * 15 // 18
        edges = np.linspace(0, rows_h, self.N_ROWS + 1).astype(int)
        # slot 0 = lowest frequency -> bottom row of the block
        self._row_bounds = [(int(edges[i]), int(edges[i + 1]))
                            for i in range(self.N_ROWS)][::-1]
        self._beat_rows = (h * 16 // 18, h)

    def reset(self) -> None:
        self._level[:] = 0.0
        self._beat_flash = 0.0

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        frame = np.zeros((ctx.height, ctx.width, 3), dtype=np.float32)
        audio = ctx.audio
        if audio is None:
            return frame.astype(np.uint8)
        decay_tau = 0.45 - 0.4 * (self.settings["decay"] / 100.0)  # 0.05-0.45 s
        fade = float(np.exp(-ctx.delta_time / max(decay_tau, 0.01)))

        sources = getattr(audio, "sources", None)
        if sources is not None:
            self._draw_sources(frame, ctx, audio, fade)
        self._draw_beat(frame, ctx, audio, fade)
        return np.clip(frame, 0, 255).astype(np.uint8)

    def _draw_sources(self, frame, ctx, audio, fade):
        sources = audio.sources
        centroids = audio.source_centroid
        n = min(self.N_ROWS, len(sources))
        for i in range(n):
            act = float(sources[i])
            # instant attack, decay-set release: a hit snaps the box bright
            # and it fades at one consistent rate
            self._level[i] = max(act, self._level[i] * fade)
            level = self._level[i]
            if level < 0.05:
                continue
            r0, r1 = self._row_bounds[i]
            col = int(np.clip(centroids[i], 0.0, 1.0) * (ctx.width - 1))
            x0 = max(0, min(col - self.BOX_W // 2, ctx.width - self.BOX_W))
            frame[r0:r1, x0:x0 + self.BOX_W] = self.ROW_COLORS[4 - i] * level

    def _draw_beat(self, frame, ctx, audio, fade):
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
                    color = self.BAR_DOWN if b == 0 else self.BAR_LIT
                    frame[r0:r1, x0:x1] = color * max(0.5, self._beat_flash)
                else:
                    frame[r0:r1, x0:x1] = self.BAR_DIM
        self._beat_flash *= fade
