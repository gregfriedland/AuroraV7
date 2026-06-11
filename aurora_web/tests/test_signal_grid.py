"""Tests for the SignalGrid drawer (RGB source rows, ADR 0005)."""

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


def features(sources=None, centroids=None, **kw):
    f = MusicFeatures(timestamp=1.0, volume=0.3, **kw)
    if sources is not None:
        f.sources = np.array(sources, dtype=np.float32)
        f.source_centroid = np.array(
            centroids if centroids is not None else np.linspace(0.1, 0.9, len(sources)),
            dtype=np.float32)
        f.source_active = (False,) * len(sources)
    return f


class TestSignalGrid:
    def test_returns_rgb(self):
        d = SignalGridDrawer(W, H)
        assert d.returns_rgb is True
        frame = d.draw(make_ctx(audio=features(sources=[1, 0, 0, 0, 0])))
        assert frame.shape == (H, W, 3)
        assert frame.dtype == np.uint8

    def test_no_audio_black(self):
        d = SignalGridDrawer(W, H)
        frame = d.draw(make_ctx(audio=None))
        assert np.all(frame == 0)

    def test_source_rows_light_by_slot(self):
        d = SignalGridDrawer(W, H)
        f = features(sources=[0.9, 0.0, 0.0, 0.0, 0.8])
        frame = d.draw(make_ctx(audio=f))
        assert np.count_nonzero(frame[12:15]) > 0, "slot 0 should be bottom"
        assert np.count_nonzero(frame[0:3]) > 0, "slot 4 should be top"
        assert np.count_nonzero(frame[3:12]) == 0, "middle slots dark"

    def test_fixed_color_per_row_dims_not_shifts(self):
        """Brightness must scale the SAME hue, not slide to another color."""
        d = SignalGridDrawer(W, H)
        bright = d.draw(make_ctx(audio=features(sources=[1.0, 0, 0, 0, 0])))
        d2 = SignalGridDrawer(W, H)
        dim = d2.draw(make_ctx(audio=features(sources=[0.4, 0, 0, 0, 0])))
        px_b = bright[13][np.nonzero(bright[13].sum(axis=1))[0][0]].astype(float)
        px_d = dim[13][np.nonzero(dim[13].sum(axis=1))[0][0]].astype(float)
        # same hue: channel ratios match (dim = bright * 0.4)
        np.testing.assert_allclose(px_d / max(px_d.max(), 1),
                                   px_b / max(px_b.max(), 1), atol=0.05)

    def test_box_crisp_fixed_width(self):
        """No fuzzy aura: the box is exactly BOX_W solid pixels."""
        d = SignalGridDrawer(W, H)
        f = features(sources=[1.0, 0, 0, 0, 0], centroids=[0.5, 1, 1, 1, 1])
        frame = d.draw(make_ctx(audio=f))
        row = frame[13].sum(axis=1)
        lit = np.nonzero(row)[0]
        assert len(lit) == SignalGridDrawer.BOX_W
        assert np.all(np.diff(lit) == 1), "box must be contiguous"
        # all box pixels identical (no soft edges)
        assert len(np.unique(frame[13][lit], axis=0)) == 1

    def test_box_x_follows_centroid(self):
        d = SignalGridDrawer(W, H)
        f_low = features(sources=[0.9, 0, 0, 0, 0], centroids=[0.1, 1, 1, 1, 1])
        x_low = np.nonzero(d.draw(make_ctx(audio=f_low))[13].sum(axis=1))[0].mean()
        d2 = SignalGridDrawer(W, H)
        f_high = features(sources=[0.9, 0, 0, 0, 0], centroids=[0.8, 1, 1, 1, 1])
        x_high = np.nonzero(d2.draw(make_ctx(audio=f_high))[13].sum(axis=1))[0].mean()
        assert x_high > x_low

    def test_hit_decays_at_consistent_rate(self):
        d = SignalGridDrawer(W, H)
        d.draw(make_ctx(audio=features(sources=[1.0, 0, 0, 0, 0])))
        quiet = features(sources=[0.0, 0, 0, 0, 0])
        levels = []
        for _ in range(60):
            frame = d.draw(make_ctx(audio=quiet))
            levels.append(frame[12:15].max())
        assert levels[0] > 0, "box should persist briefly after the hit"
        assert levels[-1] == 0, "box should decay to black"
        assert all(a >= b for a, b in zip(levels, levels[1:])), "monotonic decay"

    def test_sustained_source_holds(self):
        d = SignalGridDrawer(W, H)
        held = features(sources=[0, 0, 0.8, 0, 0])
        for _ in range(120):
            frame = d.draw(make_ctx(audio=held))
        assert np.count_nonzero(frame[6:9]) > 0, "sustained activation stays lit"

    def test_beat_row_and_downbeat_color(self):
        d = SignalGridDrawer(W, H)
        f1 = features(sources=[0, 0, 0, 0, 0], bpm=120.0, beat_now=True, beat_in_bar=1)
        for _ in range(30):  # let the silence-gate volume EMA settle
            frame1 = d.draw(make_ctx(audio=f1))
        assert np.count_nonzero(frame1[BEAT]) > 10
        d2 = SignalGridDrawer(W, H)
        f2 = features(sources=[0, 0, 0, 0, 0], bpm=120.0, beat_now=True, beat_in_bar=2)
        for _ in range(30):
            frame2 = d2.draw(make_ctx(audio=f2))
        # downbeat box (gold) differs in hue from a normal lit beat (white)
        px1 = frame1[16, 2].astype(int)
        px2 = frame2[16, 10].astype(int)
        assert px1[2] < px1[0], "downbeat should be warm (B < R)"
        assert abs(int(px2[2]) - int(px2[0])) < 30, "normal beat near-white"

    def test_works_with_old_audioinput(self):
        from aurora_web.inputs.audio_feed import AudioInput
        d = SignalGridDrawer(W, H)
        old = AudioInput(volume=0.5, spectrum=np.ones(16, dtype=np.float32) * 0.5,
                         bpm=120.0, beat_onset=True, beat_phase=0.3)
        frame = d.draw(make_ctx(audio=old))
        assert frame.shape == (H, W, 3)
        assert np.count_nonzero(frame[BEAT]) > 0  # beat row still works

    def test_reset_clears_state(self):
        d = SignalGridDrawer(W, H)
        d.draw(make_ctx(audio=features(sources=[1, 1, 1, 1, 1], bpm=120.0, beat_now=True)))
        d.reset()
        assert np.all(d._level == 0.0)
        assert d._beat_flash == 0.0

    def test_beat_row_hidden_in_silence(self):
        d = SignalGridDrawer(W, H)
        playing = features(sources=[0, 0, 0, 0, 0], bpm=120.0, beat_in_bar=2)
        for _ in range(60):
            d.draw(make_ctx(audio=playing))
        silent = features(sources=[0, 0, 0, 0, 0], bpm=120.0, beat_in_bar=2)
        silent.volume = 0.0
        for _ in range(600):  # ~10 s of silence (EMA needs ~7 s to cross)
            frame = d.draw(make_ctx(audio=silent))
        assert np.count_nonzero(frame[BEAT]) == 0, "beat row must hide in silence"
