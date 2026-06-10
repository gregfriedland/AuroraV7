"""Tests for the SignalGrid drawer (discovered source rows, ADR 0005)."""

import numpy as np

from aurora_web.drawers.base import DrawerContext
from aurora_web.drawers.signal_grid import SignalGridDrawer
from aurora_web.inputs.music_analyzer import MusicFeatures

W, H = 32, 18

SOURCE_BLOCK = slice(0, 15)
BEAT = slice(16, 18)


def make_ctx(audio=None, t=1.0):
    return DrawerContext(width=W, height=H, frame_num=1, time=t,
                         delta_time=1 / 60, palette_size=4096, audio=audio)


def features(sources=None, centroids=None, active=None, **kw):
    f = MusicFeatures(timestamp=1.0, volume=0.3, **kw)
    if sources is not None:
        f.sources = np.array(sources, dtype=np.float32)
        f.source_centroid = np.array(
            centroids if centroids is not None else np.linspace(0.1, 0.9, len(sources)),
            dtype=np.float32)
        f.source_active = tuple(active) if active is not None else (False,) * len(sources)
    return f


class TestSignalGrid:
    def test_no_audio_black(self):
        d = SignalGridDrawer(W, H)
        frame = d.draw(make_ctx(audio=None))
        assert frame.shape == (H, W)
        assert np.all(frame == 0)

    def test_source_rows_light_by_slot(self):
        d = SignalGridDrawer(W, H)
        f = features(sources=[0.9, 0.0, 0.0, 0.0, 0.8])
        frame = d.draw(make_ctx(audio=f))
        # slot 0 (lowest frequency) renders on the BOTTOM row of the block
        assert np.count_nonzero(frame[12:15]) > 0, "slot 0 should be bottom"
        assert np.count_nonzero(frame[0:3]) > 0, "slot 4 should be top"
        assert np.count_nonzero(frame[3:12]) == 0, "middle slots dark"

    def test_box_x_follows_centroid(self):
        d = SignalGridDrawer(W, H)
        f_low = features(sources=[0.9, 0, 0, 0, 0], centroids=[0.1, 1, 1, 1, 1])
        x_low = np.nonzero(d.draw(make_ctx(audio=f_low))[13])[0].mean()
        d2 = SignalGridDrawer(W, H)
        f_high = features(sources=[0.9, 0, 0, 0, 0], centroids=[0.8, 1, 1, 1, 1])
        x_high = np.nonzero(d2.draw(make_ctx(audio=f_high))[13])[0].mean()
        assert x_high > x_low

    def test_rising_edge_flash_and_decay(self):
        d = SignalGridDrawer(W, H)
        hit = features(sources=[0.0, 0, 0, 0, 0], active=[True, False, False, False, False])
        frame = d.draw(make_ctx(audio=hit))
        assert np.count_nonzero(frame[12:15]) > 0, "flash should light despite 0 activation"
        quiet = features(sources=[0.0, 0, 0, 0, 0])
        for _ in range(60):
            frame = d.draw(make_ctx(audio=quiet))
        assert np.count_nonzero(frame[12:15]) == 0, "flash should decay"

    def test_sustained_source_holds(self):
        d = SignalGridDrawer(W, H)
        held = features(sources=[0, 0, 0.8, 0, 0])
        for _ in range(120):
            frame = d.draw(make_ctx(audio=held))
        assert np.count_nonzero(frame[6:9]) > 0, "sustained activation should stay lit"

    def test_cold_start_fallback_bands(self):
        d = SignalGridDrawer(W, H)
        f = MusicFeatures(volume=0.3, bands=np.ones(16, dtype=np.float32) * 0.8)
        frame = d.draw(make_ctx(audio=f))  # sources is None
        assert np.count_nonzero(frame[SOURCE_BLOCK]) > 20, "fallback bands should show"

    def test_beat_row(self):
        d = SignalGridDrawer(W, H)
        f = features(sources=[0, 0, 0, 0, 0], bpm=120.0, beat_now=True, beat_in_bar=1)
        frame = d.draw(make_ctx(audio=f))
        assert np.count_nonzero(frame[BEAT]) > 10

    def test_downbeat_distinct_color(self):
        d = SignalGridDrawer(W, H)
        f1 = features(sources=[0, 0, 0, 0, 0], bpm=120.0, beat_now=True, beat_in_bar=1)
        frame_down = d.draw(make_ctx(audio=f1))
        d2 = SignalGridDrawer(W, H)
        f2 = features(sources=[0, 0, 0, 0, 0], bpm=120.0, beat_now=True, beat_in_bar=2)
        frame_2 = d2.draw(make_ctx(audio=f2))
        assert frame_down[16, :8].max() > frame_2[16, :8].max()

    def test_works_with_old_audioinput(self):
        from aurora_web.inputs.audio_feed import AudioInput
        d = SignalGridDrawer(W, H)
        old = AudioInput(volume=0.5, spectrum=np.ones(16, dtype=np.float32) * 0.5,
                         bpm=120.0, beat_onset=True, beat_phase=0.3)
        frame = d.draw(make_ctx(audio=old))
        assert frame.shape == (H, W)
        assert np.count_nonzero(frame) > 0  # fallback bands + beat row

    def test_reset_clears_state(self):
        d = SignalGridDrawer(W, H)
        d.draw(make_ctx(audio=features(sources=[1, 1, 1, 1, 1],
                                       active=[True] * 5, bpm=120.0, beat_now=True)))
        d.reset()
        assert np.all(d._flash == 0.0)
        assert d._beat_flash == 0.0
