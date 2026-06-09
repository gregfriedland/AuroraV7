"""Tests for BeatBouncer and external beat feed."""

import time

import numpy as np

from aurora_web.core.find_beats import ExternalBeatFeed
from aurora_web.core.drawer_manager import DrawerManager
from aurora_web.drawers.base import DrawerContext
from aurora_web.drawers.beat_bouncer import BeatBouncerDrawer


class TestExternalBeatFeed:
    """Tests for V6-style onset parsing."""

    def test_valid_onset_line_is_active(self):
        feed = ExternalBeatFeed("unused", onset_duration=1.0)
        feed._set_from_line("[1010]")

        assert feed.get_onsets() == (True, False, True, False)

    def test_invalid_onset_line_is_ignored(self):
        feed = ExternalBeatFeed("unused", verbose=False)
        feed._set_from_line("1010")

        assert feed.get_onsets() == ()

    def test_onsets_expire(self):
        feed = ExternalBeatFeed("unused", onset_duration=0.01)
        feed._set_from_line("[10]")
        time.sleep(0.02)

        assert feed.get_onsets() == (False, False)


class TestBeatBouncerDrawer:
    """Tests for BeatBouncer drawing."""

    def test_no_onsets_draws_black(self):
        drawer = BeatBouncerDrawer(8, 4, palette_size=100)
        ctx = DrawerContext(8, 4, 1, 0.0, 0.1, 100)

        result = drawer.draw(ctx)

        assert result.shape == (4, 8)
        assert np.all(result == 0)

    def test_active_onsets_draw_vertical_bands(self):
        drawer = BeatBouncerDrawer(8, 4, palette_size=100)
        drawer.update_settings({"bandHeight": 2, "color": 50})
        ctx = DrawerContext(
            width=8,
            height=4,
            frame_num=1,
            time=0.0,
            delta_time=0.1,
            palette_size=100,
            beat_onsets=(True, False, True, False),
        )

        result = drawer.draw(ctx)

        assert np.all(result[1:3, 0:2] == 50)
        assert np.all(result[1:3, 2:4] == 0)
        assert np.all(result[1:3, 4:6] == 50)
        assert np.all(result[1:3, 6:8] == 0)

    def test_drawer_manager_passes_beat_onsets_to_drawer(self):
        class FakeBeatFeed:
            def get_onsets(self):
                return (True,)

        manager = DrawerManager(4, 4, palette_size=100, beat_feed=FakeBeatFeed())
        manager.register_drawer(BeatBouncerDrawer(4, 4, palette_size=100))
        manager.set_active_drawer("BeatBouncer")
        manager.set_mode("pattern")

        result = manager.get_frame(None)

        assert result.shape == (4, 4, 3)
        assert np.any(result > 0)
