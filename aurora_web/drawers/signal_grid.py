"""SignalGrid drawer — instrument-class rows driven by MusicFeatures.

Layout on a 32x18 matrix (rows scale with matrix height):

    rows 0-4   SMOOTH instruments (harmonica/voice): a ribbon that appears
               when pitch emerges WITHOUT an attack, holds while sustained,
               wobbles/slides with vibrato and bends. x = frequency (log).
    rows 6-10  PLUCKED instruments (guitar/bass): note boxes spawned by
               onsets at the note's frequency; sustain holds them, bends
               slide them, short notes fade at the decay rate.
    rows 12-14 PERCUSSION: kick | snare | hat cells, rapid-fire flash+decay.
    row  16    beat-in-bar boxes (current beat lit, downbeat distinct)
    row  17    loudness bar (K-weighted, AGC'd, EMA-smoothed)

Smooth-vs-plucked routing: when a voiced pitch segment starts, it goes to
the plucked row if an attack (note_on or snare-band onset) happened within
the last ~120 ms, otherwise to the smooth row.
"""

import numpy as np

from aurora_web.drawers.base import Drawer, DrawerContext


class SignalGridDrawer(Drawer):
    """Instrument-class visualization of the extracted music features."""

    # Silence legitimately renders black; exempt from stuck detection
    reacts_to_audio = True

    # cents of x movement per pixel for in-note pitch deviation (magnified
    # so 50-cent vibrato is clearly visible)
    CENTS_PER_PIXEL = 18.0
    ATTACK_WINDOW = 0.12     # s: onset within this window => plucked

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("SignalGrid", width, height, palette_size)
        self.settings = {
            "decay": 50,        # flash decay speed
        }
        self.settings_ranges = {
            "decay": (10, 100),
        }
        self._perc_flash = {"kick": 0.0, "snare": 0.0, "hat": 0.0}
        self._beat_flash = 0.0
        self._smoothed_loudness = 0.0

        # voiced-segment state shared by smooth/plucked rows
        self._voiced = False
        self._segment_plucked = False
        self._base_cents = 0.0
        self._x = 0.0
        self._smooth_level = 0.0
        self._pluck_level = 0.0
        self._last_attack_time = -1e9

        # row layout, scaled to matrix height (designed for 18)
        h = height
        self._smooth_rows = (0, max(1, h * 5 // 18))              # 0-4
        self._pluck_rows = (h * 6 // 18, h * 11 // 18)            # 6-10
        self._perc_rows = (h * 12 // 18, h * 15 // 18)            # 12-14
        self._beat_row = (h * 16 // 18, max(h * 16 // 18 + 1, h * 17 // 18))  # 16
        self._loud_row = min(h - 1, h * 17 // 18)                 # 17

    def reset(self) -> None:
        self._perc_flash = {"kick": 0.0, "snare": 0.0, "hat": 0.0}
        self._beat_flash = 0.0
        self._smooth_level = 0.0
        self._pluck_level = 0.0
        self._voiced = False

    # Palette color slots (fractions of palette size)
    def _colors(self, ps: int) -> dict:
        return {
            "smooth": ps * 2 // 5,
            "pluck": ps * 4 // 5,
            "kick": ps * 1 // 5,
            "snare": ps * 2 // 5,
            "hat": ps * 3 // 5,
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

        self._track_note(audio, ctx)
        self._draw_smooth(indices, ctx, c, fade)
        self._draw_plucked(indices, ctx, c, fade)
        self._draw_percussion(indices, ctx, audio, c)
        self._draw_beat(indices, ctx, audio, c, fade)
        self._draw_loudness(indices, ctx, audio, c)
        return indices

    # ------------------------------------------------------------------
    # Shared voiced-note tracking + smooth/plucked routing
    # ------------------------------------------------------------------
    def _track_note(self, audio, ctx):
        now = getattr(audio, "timestamp", ctx.time)
        f0 = getattr(audio, "f0_hz", 0.0)
        conf = getattr(audio, "pitch_confidence", 0.0)
        volume = getattr(audio, "volume", 0.0)
        voiced = bool(f0 and f0 > 0 and conf > 0.3 and volume > 0.005)

        # attacks: explicit note events or mid-band percussive onsets
        if getattr(audio, "note_on", False) or getattr(audio, "onset_snare", False):
            self._last_attack_time = now

        if voiced:
            cents = 1200.0 * np.log2(f0 / 55.0)
            new_segment = (
                not self._voiced
                or getattr(audio, "note_on", False)
                or abs(cents - self._base_cents) > 300  # jumped >3 semitones
            )
            if new_segment:
                self._base_cents = cents
                self._x = float(np.clip(cents / 6000.0, 0.0, 1.0) * (ctx.width - 1))
                self._segment_plucked = (now - self._last_attack_time) < self.ATTACK_WINDOW
                if self._segment_plucked:
                    self._pluck_level = 1.0
                else:
                    self._smooth_level = 1.0
            else:
                deviation = cents - self._base_cents
                base_x = float(np.clip(self._base_cents / 6000.0, 0.0, 1.0) * (ctx.width - 1))
                self._x = base_x + deviation / self.CENTS_PER_PIXEL
                sustain = getattr(audio, "sustain_level", None)
                level = sustain if sustain is not None else min(1.0, volume * 6)
                if self._segment_plucked:
                    self._pluck_level = max(0.35, float(level))
                else:
                    self._smooth_level = max(0.35, float(level))
        self._voiced = voiced

    def _draw_smooth(self, indices, ctx, c, fade):
        """Harmonica/voice: ribbon present only while the tone sounds."""
        r0, r1 = self._smooth_rows
        if not (self._voiced and not self._segment_plucked):
            self._smooth_level *= fade
        if self._smooth_level > 0.03:
            col = int(np.clip(self._x, 0, ctx.width - 1))
            x0, x1 = max(0, col - 2), min(ctx.width, col + 3)
            indices[r0:r1, x0:x1] = self._scaled(c["smooth"], self._smooth_level)
            # soft edges one pixel wider, half brightness
            if x0 > 0:
                indices[r0:r1, x0 - 1] = self._scaled(c["smooth"], self._smooth_level * 0.4)
            if x1 < ctx.width:
                indices[r0:r1, x1] = self._scaled(c["smooth"], self._smooth_level * 0.4)

    def _draw_plucked(self, indices, ctx, c, fade):
        """Guitar/bass: onset-spawned box, holds on sustain, slides on bend."""
        r0, r1 = self._pluck_rows
        if not (self._voiced and self._segment_plucked):
            self._pluck_level *= fade
        if self._pluck_level > 0.03:
            col = int(np.clip(self._x, 0, ctx.width - 1))
            x0, x1 = max(0, col - 1), min(ctx.width, col + 2)
            indices[r0:r1, x0:x1] = self._scaled(c["pluck"], self._pluck_level)

    def _draw_percussion(self, indices, ctx, audio, c):
        """Drums: rapid-fire cells. Fast fixed decay so consecutive
        hits read as separate flashes even at high rates."""
        r0, r1 = self._perc_rows
        cells = [
            ("kick", getattr(audio, "onset_kick", False), getattr(audio, "kick_strength", 0.0)),
            ("snare", getattr(audio, "onset_snare", False), getattr(audio, "snare_strength", 0.0)),
            ("hat", getattr(audio, "onset_hat", False), getattr(audio, "hat_strength", 0.0)),
        ]
        fast_fade = float(np.exp(-ctx.delta_time / 0.06))
        cell_w = ctx.width // 3
        for i, (name, fired, strength) in enumerate(cells):
            if fired:
                self._perc_flash[name] = max(0.5, strength)
            level = self._perc_flash[name]
            if level > 0.02:
                x0 = i * cell_w
                x1 = ctx.width if i == 2 else x0 + cell_w - 1
                indices[r0:r1, x0:x1] = self._scaled(c[name], level)
            self._perc_flash[name] *= fast_fade

    def _draw_beat(self, indices, ctx, audio, c, fade):
        """Four beat-in-bar boxes; current beat lit, downbeat distinct."""
        r0, r1 = self._beat_row
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
