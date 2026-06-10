"""SignalGrid drawer — organized visualization of every MusicFeatures signal.

Layout on a 32x18 matrix (rows scale with matrix height):

    rows 0-5   band energy columns (16 bands x 2 px, GEQ-style bars)
    rows 7-8   band onsets: kick | snare | hat cells, flash + decay
    rows 10-12 note box: appears at the note's frequency on onset, holds
               while sustained, slides/wobbles in x with bends and vibrato
               (live f0, deviation magnified), fades on release
    rows 14-15 beat-in-bar boxes (current beat lit, downbeat distinct)
    row  17    loudness bar (K-weighted, AGC'd)
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
        self._beat_flash = 0.0
        self._smoothed_loudness = 0.0
        # note-box state: the box lives as long as the note does
        self._note_level = 0.0       # brightness; holds while sustained
        self._note_base_cents = 0.0  # pitch at note onset (anchors x position)
        self._note_x = 0.0

        # row layout, scaled to matrix height (designed for 18)
        h = height
        self._bands_rows = (0, max(1, h * 6 // 18))               # 0-5
        self._onset_rows = (h * 7 // 18, h * 9 // 18)             # 7-8
        self._note_rows = (h * 10 // 18, h * 13 // 18)            # 10-12
        self._beat_rows = (h * 14 // 18, h * 16 // 18)            # 14-15
        self._loud_row = min(h - 1, h * 17 // 18)                 # 17

    def reset(self) -> None:
        self._onset_flash = {"kick": 0.0, "snare": 0.0, "hat": 0.0}
        self._beat_flash = 0.0
        self._note_level = 0.0

    # Palette color slots (fractions of palette size, like AudioViz)
    def _colors(self, ps: int) -> dict:
        return {
            "bands": ps * 2 // 5,
            "kick": ps * 1 // 5,
            "snare": ps * 2 // 5,
            "hat": ps * 3 // 5,
            "note": ps * 4 // 5,
            "bar": ps * 3 // 5,
            "downbeat": ps - 1,
            "loud": ps * 3 // 5,
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
        self._draw_note(indices, ctx, audio, c, fade)
        self._draw_beat(indices, ctx, audio, c, fade)
        self._draw_loudness(indices, ctx, audio, c)
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

    # cents of x movement per pixel for in-note pitch deviation. True scale
    # (one octave = ~6.4 px) would make a 50-cent vibrato invisible (~0.3 px),
    # so deviation from the note's starting pitch is magnified.
    CENTS_PER_PIXEL = 18.0

    def _draw_note(self, indices, ctx, audio, c, fade):
        """One box per note, alive for the note's whole life.

        Onset: box appears at the note's frequency (log-x). Sustain: box
        holds. Bend/vibrato: the box slides/wobbles in x, tracking the live
        f0 (deviation from the onset pitch, magnified to be visible).
        Release/short note: box fades at the decay rate.
        """
        r0, r1 = self._note_rows
        f0 = getattr(audio, "f0_hz", 0.0)
        conf = getattr(audio, "pitch_confidence", 0.0)
        volume = getattr(audio, "volume", 0.0)
        voiced = bool(f0 and f0 > 0 and conf > 0.3 and volume > 0.005)

        if voiced:
            cents = 1200.0 * np.log2(f0 / 55.0)
            new_note = (
                getattr(audio, "note_on", False)
                or self._note_level < 0.05
                or abs(cents - self._note_base_cents) > 300  # jumped >3 semitones
            )
            if new_note:
                self._note_base_cents = cents
                # base x from absolute pitch: 55 Hz (A1) .. 1760 Hz (A6), log
                self._note_x = float(np.clip(cents / 6000.0, 0.0, 1.0) * (ctx.width - 1))
                self._note_level = 1.0
            else:
                # the box follows the live pitch: bends slide it, vibrato
                # wobbles it around the onset position
                deviation = cents - self._note_base_cents
                base_x = float(np.clip(self._note_base_cents / 6000.0, 0.0, 1.0) * (ctx.width - 1))
                self._note_x = base_x + deviation / self.CENTS_PER_PIXEL
                # held note: brightness tracks the envelope, never below a
                # visible floor while the note sounds
                sustain = getattr(audio, "sustain_level", None)
                level = sustain if sustain is not None else min(1.0, volume * 6)
                self._note_level = max(0.35, float(level))
        else:
            # note ended (or was short): fade out in place
            self._note_level *= fade

        if self._note_level > 0.03:
            col = int(np.clip(self._note_x, 0, ctx.width - 1))
            x0, x1 = max(0, col - 1), min(ctx.width, col + 2)
            indices[r0:r1, x0:x1] = self._scaled(c["note"], self._note_level)

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
        # time-based EMA (~80 ms) smooths bar jitter without adding much lag
        a = 1.0 - float(np.exp(-ctx.delta_time / 0.08))
        self._smoothed_loudness += a * (float(loud) - self._smoothed_loudness)
        level = self._smoothed_loudness
        fill = int(np.clip(level, 0.0, 1.0) * ctx.width)
        if fill > 0:
            indices[row, :fill] = self._scaled(c["loud"], 0.4 + 0.6 * level)
