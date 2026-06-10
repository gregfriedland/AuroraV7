"""Tests for the SignalGrid drawer (instrument-class rows)."""

import numpy as np

from aurora_web.drawers.base import DrawerContext
from aurora_web.drawers.signal_grid import SignalGridDrawer
from aurora_web.inputs.music_analyzer import MusicFeatures

W, H = 32, 18

SMOOTH = slice(0, 5)
PLUCK = slice(6, 11)
PERC = slice(12, 15)
BEAT = 16
LOUD = 17


def make_ctx(audio=None, t=1.0):
    return DrawerContext(width=W, height=H, frame_num=1, time=t,
                         delta_time=1 / 60, palette_size=4096, audio=audio)


def tone(f0=440.0, note_on=False, snare=False, ts=1.0, volume=0.3, sustain=0.8):
    return MusicFeatures(
        timestamp=ts, f0_hz=f0, pitch_confidence=0.9, volume=volume,
        sustain_level=sustain, note_on=note_on, onset_snare=snare,
        bands=np.zeros(16, dtype=np.float32),
    )


def drums(ts=1.0):
    return MusicFeatures(
        timestamp=ts, volume=0.4,
        onset_kick=True, kick_strength=0.9,
        onset_snare=True, snare_strength=0.6,
        onset_hat=True, hat_strength=0.4,
        bands=np.zeros(16, dtype=np.float32),
    )


class TestSignalGrid:
    def test_no_audio_black(self):
        d = SignalGridDrawer(W, H)
        frame = d.draw(make_ctx(audio=None))
        assert frame.shape == (H, W)
        assert np.all(frame == 0)

    def test_zero_features_near_black(self):
        d = SignalGridDrawer(W, H)
        frame = d.draw(make_ctx(audio=MusicFeatures()))
        assert np.count_nonzero(frame) == 0

    def test_smooth_tone_without_attack_goes_to_smooth_row(self):
        """Harmonica: pitch fades in with no onset -> smooth row only."""
        d = SignalGridDrawer(W, H)
        frame = d.draw(make_ctx(audio=tone(note_on=False)))
        assert np.count_nonzero(frame[SMOOTH]) > 0, "smooth row should light"
        assert np.count_nonzero(frame[PLUCK]) == 0, "plucked row should stay dark"

    def test_attacked_note_goes_to_plucked_row(self):
        """Guitar: note arrives with an onset -> plucked row only."""
        d = SignalGridDrawer(W, H)
        frame = d.draw(make_ctx(audio=tone(note_on=True)))
        assert np.count_nonzero(frame[PLUCK]) > 0, "plucked row should light"
        assert np.count_nonzero(frame[SMOOTH]) == 0, "smooth row should stay dark"

    def test_plucked_note_sustains_then_fades(self):
        d = SignalGridDrawer(W, H)
        d.draw(make_ctx(audio=tone(note_on=True, ts=1.0)))
        for i in range(120):  # 2 s sustain, no new onsets
            frame = d.draw(make_ctx(audio=tone(ts=1.0 + i / 60)))
        assert np.count_nonzero(frame[PLUCK]) > 0, "box should hold during sustain"
        silent = MusicFeatures(bands=np.zeros(16, dtype=np.float32))
        for _ in range(120):
            frame = d.draw(make_ctx(audio=silent))
        assert np.count_nonzero(frame[PLUCK]) == 0, "box should fade after release"

    def test_bend_slides_plucked_box(self):
        d = SignalGridDrawer(W, H)
        d.draw(make_ctx(audio=tone(220.0, note_on=True, ts=1.0)))
        frame = d.draw(make_ctx(audio=tone(220.0, ts=1.02)))
        x_start = int(np.mean(np.nonzero(frame[6])[0]))
        bent = tone(220.0 * 2 ** (200 / 1200), ts=1.05)
        frame = d.draw(make_ctx(audio=bent))
        x_bent = int(np.mean(np.nonzero(frame[6])[0]))
        assert x_bent > x_start, "bend should slide the box right"

    def test_vibrato_moves_smooth_ribbon(self):
        d = SignalGridDrawer(W, H)
        d.draw(make_ctx(audio=tone(440.0, ts=1.0)))
        frame = d.draw(make_ctx(audio=tone(440.0, ts=1.02)))
        x_center = int(np.mean(np.nonzero(frame[0])[0]))
        up = tone(440.0 * 2 ** (40 / 1200), ts=1.04)  # +40 cents
        frame = d.draw(make_ctx(audio=up))
        x_up = int(np.mean(np.nonzero(frame[0])[0]))
        assert x_up > x_center, "pitch wobble should move the ribbon"

    def test_position_scales_with_f0(self):
        cols = []
        for f0 in (110.0, 880.0):
            d = SignalGridDrawer(W, H)
            frame = d.draw(make_ctx(audio=tone(f0)))
            lit = np.nonzero(frame[0])[0]
            assert len(lit) > 0
            cols.append(int(np.mean(lit)))
        assert cols[1] > cols[0], "higher pitch should light further right"

    def test_percussion_cells_flash_and_decay_fast(self):
        d = SignalGridDrawer(W, H)
        frame = d.draw(make_ctx(audio=drums()))
        assert np.count_nonzero(frame[PERC]) > 10, "all three cells should flash"
        silent = MusicFeatures(bands=np.zeros(16, dtype=np.float32))
        for _ in range(30):  # 0.5 s
            frame = d.draw(make_ctx(audio=silent))
        assert np.count_nonzero(frame[PERC]) == 0, "percussion decays fast"

    def test_beat_and_loudness_rows(self):
        d = SignalGridDrawer(W, H)
        f = MusicFeatures(bpm=120.0, beat_now=True, beat_in_bar=1,
                          downbeat_now=True, loudness=0.8,
                          bands=np.zeros(16, dtype=np.float32))
        for _ in range(30):
            frame = d.draw(make_ctx(audio=f))
        assert np.count_nonzero(frame[BEAT]) > 10
        assert np.count_nonzero(frame[LOUD]) > 10

    def test_downbeat_distinct_color(self):
        d = SignalGridDrawer(W, H)
        f1 = MusicFeatures(bpm=120.0, beat_now=True, beat_in_bar=1,
                           bands=np.zeros(16, dtype=np.float32))
        frame_down = d.draw(make_ctx(audio=f1))
        d2 = SignalGridDrawer(W, H)
        f2 = MusicFeatures(bpm=120.0, beat_now=True, beat_in_bar=2,
                           bands=np.zeros(16, dtype=np.float32))
        frame_2 = d2.draw(make_ctx(audio=f2))
        assert frame_down[BEAT, :8].max() > frame_2[BEAT, :8].max()

    def test_works_with_old_audioinput(self):
        from aurora_web.inputs.audio_feed import AudioInput
        d = SignalGridDrawer(W, H)
        old = AudioInput(volume=0.5, spectrum=np.ones(16, dtype=np.float32) * 0.5,
                         bpm=120.0, beat_onset=True, beat_phase=0.3)
        frame = d.draw(make_ctx(audio=old))
        assert frame.shape == (H, W)
        assert np.count_nonzero(frame) > 0

    def test_reset_clears_state(self):
        d = SignalGridDrawer(W, H)
        d.draw(make_ctx(audio=drums()))
        d.draw(make_ctx(audio=tone(note_on=True)))
        d.reset()
        assert all(v == 0.0 for v in d._perc_flash.values())
        assert d._beat_flash == 0.0
        assert d._smooth_level == 0.0 and d._pluck_level == 0.0
