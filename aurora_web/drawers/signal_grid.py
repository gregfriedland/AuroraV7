"""SignalGrid drawer — organized visualization of every MusicFeatures signal.

Layout on a 32x18 matrix (rows scale with matrix height):

    rows 0-5   band energy columns (16 bands x 2 px, GEQ-style bars)
    rows 7-8   drum onsets: kick | snare | hat cells, flash + decay
    rows 10-11 pitch: lit column = f0 (log scale), vibrato wobbles it,
               note_on flashes it
    rows 13-14 beat: phase sweep (left) + beat-in-bar boxes (right,
               downbeat in a distinct color)
    row  16    loudness bar (K-weighted, AGC'd)
    row  17    expressive cells: vibrato/tremolo/sustain/bend/noisiness/brightness
"""

import numpy as np

from aurora_web.drawers.base import Drawer, DrawerContext


class SignalGridDrawer(Drawer):
    """Debug/reference grid showing all extracted music features."""

    # Silence legitimately renders black; exempt from stuck detection
    reacts_to_audio = True

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("SignalGrid", width, height, palette_size)
        self.settings = {
            "decay": 50,        # flash decay speed
        }
        self.settings_ranges = {
            "decay": (10, 100),
        }
        self._onset_flash = {"kick": 0.0, "snare": 0.0, "hat": 0.0}
        self._pitch_flash = 0.0
        self._beat_flash = 0.0

        # row layout, scaled to matrix height (designed for 18)
        h = height
        self._bands_rows = (0, max(1, h * 6 // 18))               # 0-5
        self._onset_rows = (h * 7 // 18, h * 9 // 18)             # 7-8
        self._pitch_rows = (h * 10 // 18, h * 12 // 18)           # 10-11
        self._beat_rows = (h * 13 // 18, h * 15 // 18)            # 13-14
        self._loud_row = min(h - 2, h * 16 // 18)                 # 16
        self._expr_row = min(h - 1, h * 17 // 18)                 # 17

    def reset(self) -> None:
        self._onset_flash = {"kick": 0.0, "snare": 0.0, "hat": 0.0}
        self._pitch_flash = 0.0
        self._beat_flash = 0.0

    # Palette color slots (fractions of palette size, like AudioViz)
    def _colors(self, ps: int) -> dict:
        return {
            "bands": ps * 2 // 5,
            "kick": ps * 1 // 5,
            "snare": ps * 2 // 5,
            "hat": ps * 3 // 5,
            "pitch": ps * 4 // 5,
            "beat": ps * 1 // 5,
            "bar": ps * 3 // 5,
            "downbeat": ps - 1,
            "loud": ps * 3 // 5,
            "expr": ps * 4 // 5,
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

        self._draw_bands(indices, ctx, audio, c)
        self._draw_onsets(indices, ctx, audio, c, fade)
        self._draw_pitch(indices, ctx, audio, c, fade)
        self._draw_beat(indices, ctx, audio, c, fade)
        self._draw_loudness(indices, ctx, audio, c)
        self._draw_expressive(indices, ctx, audio, c)
        return indices

    def _draw_bands(self, indices, ctx, audio, c):
        bands = getattr(audio, "bands", None)
        if bands is None:
            bands = getattr(audio, "spectrum", None)
        if bands is None:
            return
        r0, r1 = self._bands_rows
        rows = r1 - r0
        n = len(bands)
        col_w = max(1, ctx.width // n)
        for i in range(min(n, ctx.width // col_w)):
            level = float(np.clip(bands[i], 0.0, 1.0))
            filled = int(round(level * rows))
            if filled == 0:
                continue
            x0 = i * col_w
            # bars grow upward from the bottom of the section
            indices[r1 - filled:r1, x0:x0 + col_w] = self._scaled(
                c["bands"], 0.4 + 0.6 * level)

    def _draw_onsets(self, indices, ctx, audio, c, fade):
        r0, r1 = self._onset_rows
        cells = [
            ("kick", getattr(audio, "onset_kick", False), getattr(audio, "kick_strength", 0.0)),
            ("snare", getattr(audio, "onset_snare", False), getattr(audio, "snare_strength", 0.0)),
            ("hat", getattr(audio, "onset_hat", False), getattr(audio, "hat_strength", 0.0)),
        ]
        cell_w = ctx.width // 3
        for i, (name, fired, strength) in enumerate(cells):
            if fired:
                self._onset_flash[name] = max(0.4, strength)
            level = self._onset_flash[name]
            if level > 0.02:
                x0 = i * cell_w
                x1 = ctx.width if i == 2 else x0 + cell_w - 1
                indices[r0:r1, x0:x1] = self._scaled(c[name], level)
            self._onset_flash[name] *= fade

    def _draw_pitch(self, indices, ctx, audio, c, fade):
        r0, r1 = self._pitch_rows
        f0 = getattr(audio, "f0_hz", 0.0)
        conf = getattr(audio, "pitch_confidence", 0.0)
        if getattr(audio, "note_on", False):
            self._pitch_flash = 1.0
        if f0 and f0 > 0 and conf > 0.3:
            # map 55 Hz (A1) .. 1760 Hz (A6) -> 0 .. width, log scale
            col = int(np.clip(np.log2(f0 / 55.0) / 5.0, 0.0, 1.0) * (ctx.width - 1))
            # vibrato wobbles the dot at its detected rate
            vib = getattr(audio, "vibrato_amount", 0.0)
            if vib > 0.1:
                rate = max(getattr(audio, "vibrato_rate", 5.0), 0.5)
                col += int(round(np.sin(2 * np.pi * rate * ctx.time) * 2 * vib))
                col = int(np.clip(col, 0, ctx.width - 1))
            brightness = float(np.clip(conf, 0.3, 1.0))
            brightness = min(1.0, brightness + self._pitch_flash)
            x0, x1 = max(0, col - 1), min(ctx.width, col + 2)
            indices[r0:r1, x0:x1] = self._scaled(c["pitch"], brightness)
        self._pitch_flash *= fade

    def _draw_beat(self, indices, ctx, audio, c, fade):
        """Four full-width beat-in-bar boxes; current beat lit, downbeat distinct."""
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
                    brightness = max(0.5, self._beat_flash)
                    indices[r0:r1, x0:x1] = self._scaled(color, brightness)
                else:
                    indices[r0:r1, x0:x1] = self._scaled(c["bar"], 0.15)
        self._beat_flash *= fade

    def _draw_loudness(self, indices, ctx, audio, c):
        row = self._loud_row
        loud = getattr(audio, "loudness", None)
        if loud is None:
            loud = getattr(audio, "volume", 0.0)
        fill = int(np.clip(loud, 0.0, 1.0) * ctx.width)
        if fill > 0:
            indices[row, :fill] = self._scaled(c["loud"], 0.4 + 0.6 * loud)

    def _draw_expressive(self, indices, ctx, audio, c):
        row = self._expr_row
        cells = [
            getattr(audio, "vibrato_amount", 0.0),
            getattr(audio, "tremolo_amount", 0.0),
            getattr(audio, "sustain_level", 0.0),
            abs(getattr(audio, "bend_amount", 0.0)),
            getattr(audio, "noisiness", 0.0),
            getattr(audio, "brightness", 0.0),
        ]
        cell_w = max(1, ctx.width // len(cells))
        for i, level in enumerate(cells):
            level = float(np.clip(level, 0.0, 1.0))
            if level < 0.05:
                continue
            x0 = i * cell_w
            x1 = ctx.width if i == len(cells) - 1 else x0 + cell_w - 1
            indices[row, x0:x1] = self._scaled(c["expr"], level)
