"""Tests for the SignalGrid drawer."""

import numpy as np

from aurora_web.drawers.base import DrawerContext
from aurora_web.drawers.signal_grid import SignalGridDrawer
from aurora_web.inputs.music_analyzer import MusicFeatures

W, H = 32, 18


def make_ctx(audio=None, t=1.0):
    return DrawerContext(width=W, height=H, frame_num=1, time=t,
                         delta_time=1 / 60, palette_size=4096, audio=audio)


def rich_features():
    return MusicFeatures(
        timestamp=1.0,
        volume=0.4,
        loudness=0.7,
        bands=np.linspace(0.1, 1.0, 16).astype(np.float32),
        onset_kick=True, kick_strength=0.9,
        onset_snare=True, snare_strength=0.6,
        onset_hat=True, hat_strength=0.4,
        f0_hz=440.0, pitch_confidence=0.9, note_on=True,
        bpm=120.0, beat_phase=0.5, beat_now=True, beat_in_bar=1,
        downbeat_now=True,
        vibrato_amount=0.5, vibrato_rate=6.0,
        tremolo_amount=0.4, bend_amount=0.3,
        envelope_state="sustain", sustain_level=0.8,
        brightness=0.6, noisiness=0.3,
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

    def test_rich_features_light_all_sections(self):
        d = SignalGridDrawer(W, H)
        frame = d.draw(make_ctx(audio=rich_features()))
        # band bars (rows 0-5)
        assert np.count_nonzero(frame[0:6]) > 10
        # onset row (rows 7-8)
        assert np.count_nonzero(frame[7:9]) > 10
        # note box (rows 10-12)
        assert np.count_nonzero(frame[10:13]) > 0
        # beat row (rows 14-15)
        assert np.count_nonzero(frame[14:16]) > 10
        # loudness row
        assert np.count_nonzero(frame[17]) > 10

    def test_onset_flash_decays(self):
        d = SignalGridDrawer(W, H)
        f = rich_features()
        d.draw(make_ctx(audio=f))
        quiet = MusicFeatures(bands=np.zeros(16, dtype=np.float32), bpm=None)
        last = None
        for _ in range(60):
            frame = d.draw(make_ctx(audio=quiet))
            last = frame
        assert np.count_nonzero(last[7:9]) == 0, "onset flash should decay away"

    def test_downbeat_distinct_color(self):
        d = SignalGridDrawer(W, H)
        f = rich_features()
        frame_down = d.draw(make_ctx(audio=f))
        d2 = SignalGridDrawer(W, H)
        f2 = rich_features()
        f2.beat_in_bar = 2
        f2.downbeat_now = False
        frame_2 = d2.draw(make_ctx(audio=f2))
        box_region = frame_down[14:16, :8]
        box_region_2 = frame_2[14:16, :8]
        assert box_region.max() > box_region_2.max(), \
            "downbeat box should use the brightest palette slot"

    def test_note_position_scales_with_f0(self):
        cols = []
        for f0 in (110.0, 880.0):
            d = SignalGridDrawer(W, H)
            f = MusicFeatures(f0_hz=f0, pitch_confidence=0.9, volume=0.3,
                              bands=np.zeros(16, dtype=np.float32))
            frame = d.draw(make_ctx(audio=f))
            lit = np.nonzero(frame[10])[0]
            assert len(lit) > 0, f"note row dark for f0={f0}"
            cols.append(int(np.mean(lit)))
        assert cols[1] > cols[0], "higher pitch should light further right"

    def test_note_box_holds_while_sustained_then_fades(self):
        d = SignalGridDrawer(W, H)
        held = MusicFeatures(f0_hz=220.0, pitch_confidence=0.9, volume=0.3,
                             sustain_level=0.8,
                             bands=np.zeros(16, dtype=np.float32))
        for _ in range(120):  # 2 s of sustain at 60 fps
            frame = d.draw(make_ctx(audio=held))
        assert np.count_nonzero(frame[10:13]) > 0, "box should hold during sustain"
        silent = MusicFeatures(bands=np.zeros(16, dtype=np.float32))
        for _ in range(120):
            frame = d.draw(make_ctx(audio=silent))
        assert np.count_nonzero(frame[10:13]) == 0, "box should fade after release"

    def test_note_box_moves_with_bend(self):
        d = SignalGridDrawer(W, H)
        def feats(f0):
            return MusicFeatures(f0_hz=f0, pitch_confidence=0.9, volume=0.3,
                                 sustain_level=0.8,
                                 bands=np.zeros(16, dtype=np.float32))
        d.draw(make_ctx(audio=feats(220.0)))         # note onset at 220 Hz
        x_start = int(np.mean(np.nonzero(d.draw(make_ctx(audio=feats(220.0)))[10])[0]))
        # bend up a whole step (+200 cents) without a new note_on
        frame = d.draw(make_ctx(audio=feats(220.0 * 2 ** (200 / 1200))))
        x_bent = int(np.mean(np.nonzero(frame[10])[0]))
        assert x_bent > x_start, "bend should slide the box right"

    def test_works_with_old_audioinput(self):
        from aurora_web.inputs.audio_feed import AudioInput
        d = SignalGridDrawer(W, H)
        old = AudioInput(volume=0.5, spectrum=np.ones(16, dtype=np.float32) * 0.5,
                         bpm=120.0, beat_onset=True, beat_phase=0.3)
        frame = d.draw(make_ctx(audio=old))
        assert frame.shape == (H, W)
        assert np.count_nonzero(frame) > 0

    def test_reset_clears_flashes(self):
        d = SignalGridDrawer(W, H)
        d.draw(make_ctx(audio=rich_features()))
        d.reset()
        assert all(v == 0.0 for v in d._onset_flash.values())
        assert d._beat_flash == 0.0
