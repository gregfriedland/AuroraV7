"""Tests for CameraDrawer class."""

import numpy as np
import pytest

from aurora_web.drawers.base import DrawerContext
from aurora_web.drawers.camera import CameraDrawer
from aurora_web.inputs.video_feed import VideoInput


class FakeVideoFeed:
    """Minimal fake video feed for testing."""

    def __init__(self, width=320, height=240):
        self.width = width
        self.height = height
        self._frame = None
        self._motion_map = None
        self._motion_amount = 0.0

    def set_frame(self, frame: np.ndarray):
        self._frame = frame

    def set_motion_map(self, motion_map: np.ndarray, amount: float = 0.5):
        self._motion_map = motion_map
        self._motion_amount = amount

    def get_input(self) -> VideoInput:
        return VideoInput(
            frame=self._frame,
            motion_amount=self._motion_amount,
            motion_map=self._motion_map,
            light_level=0.5,
            dominant_color=(128, 128, 128),
            faces=None,
        )


def make_ctx(width=32, height=18, t=0.0):
    return DrawerContext(
        width=width, height=height, frame_num=0, time=t, delta_time=0.016
    )


class TestCameraDrawerInit:
    """Tests for initialization."""

    def test_initialization(self):
        drawer = CameraDrawer(32, 18)
        assert drawer.name == "Camera"
        assert drawer.width == 32
        assert drawer.height == 18
        assert drawer.palette_size == 4096

    def test_has_settings(self):
        drawer = CameraDrawer(32, 18)
        assert "mode" in drawer.settings
        assert "brightness" in drawer.settings
        assert "contrast" in drawer.settings
        assert "mirror" in drawer.settings

    def test_settings_have_ranges(self):
        drawer = CameraDrawer(32, 18)
        for key in drawer.settings:
            assert key in drawer.settings_ranges


class TestCameraDrawerNoFeed:
    """Tests when no video feed is available."""

    def test_draw_without_feed_returns_correct_shape(self):
        drawer = CameraDrawer(32, 18)
        result = drawer.draw(make_ctx())
        assert result.shape == (18, 32)
        assert result.dtype == np.int32

    def test_draw_without_feed_returns_valid_indices(self):
        drawer = CameraDrawer(32, 18)
        result = drawer.draw(make_ctx())
        assert np.all(result >= 0)
        assert np.all(result < 4096)

    def test_fallback_animates(self):
        """Fallback pattern should change with time."""
        drawer = CameraDrawer(32, 18)
        frame1 = drawer.draw(make_ctx(t=0.0))
        frame2 = drawer.draw(make_ctx(t=1.0))
        assert not np.array_equal(frame1, frame2)


class TestCameraDrawerLuminance:
    """Tests for luminance (default) mode."""

    def test_draw_with_feed_returns_correct_shape(self):
        feed = FakeVideoFeed()
        feed.set_frame(np.full((240, 320, 3), 128, dtype=np.uint8))
        drawer = CameraDrawer(32, 18, video_feed=feed)
        result = drawer.draw(make_ctx())
        assert result.shape == (18, 32)
        assert result.dtype == np.int32

    def test_draw_returns_valid_indices(self):
        feed = FakeVideoFeed()
        feed.set_frame(np.random.randint(0, 256, (240, 320, 3), dtype=np.uint8))
        drawer = CameraDrawer(32, 18, video_feed=feed)
        result = drawer.draw(make_ctx())
        assert np.all(result >= 0)
        assert np.all(result < 4096)

    def test_black_frame_maps_to_low_indices(self):
        feed = FakeVideoFeed()
        feed.set_frame(np.zeros((240, 320, 3), dtype=np.uint8))
        drawer = CameraDrawer(32, 18, video_feed=feed)
        # Set brightness/contrast to neutral
        drawer.settings["brightness"] = 50
        drawer.settings["contrast"] = 50
        result = drawer.draw(make_ctx())
        # Black input -> low palette indices
        assert np.mean(result) < self._midpoint(drawer)

    def test_white_frame_maps_to_high_indices(self):
        feed = FakeVideoFeed()
        feed.set_frame(np.full((240, 320, 3), 255, dtype=np.uint8))
        drawer = CameraDrawer(32, 18, video_feed=feed)
        drawer.settings["brightness"] = 50
        drawer.settings["contrast"] = 50
        result = drawer.draw(make_ctx())
        # White input -> high palette indices
        assert np.mean(result) > self._midpoint(drawer)

    def test_gradient_frame_produces_varying_indices(self):
        """A gradient input should produce varying output indices."""
        feed = FakeVideoFeed()
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        # Horizontal gradient
        for x in range(320):
            frame[:, x, :] = int(x / 319 * 255)
        feed.set_frame(frame)
        drawer = CameraDrawer(32, 18, video_feed=feed)
        result = drawer.draw(make_ctx())
        # Should have variety in values
        assert result.max() - result.min() > 100

    @staticmethod
    def _midpoint(drawer):
        return drawer.palette_size / 2


class TestCameraDrawerEdgeMode:
    """Tests for edge-detection mode."""

    def test_edge_mode_returns_correct_shape(self):
        feed = FakeVideoFeed()
        feed.set_frame(np.random.randint(0, 256, (240, 320, 3), dtype=np.uint8))
        drawer = CameraDrawer(32, 18, video_feed=feed)
        drawer.settings["mode"] = CameraDrawer.MODE_EDGES
        result = drawer.draw(make_ctx())
        assert result.shape == (18, 32)

    def test_uniform_frame_has_no_edges(self):
        feed = FakeVideoFeed()
        feed.set_frame(np.full((240, 320, 3), 128, dtype=np.uint8))
        drawer = CameraDrawer(32, 18, video_feed=feed)
        drawer.settings["mode"] = CameraDrawer.MODE_EDGES
        drawer.settings["brightness"] = 50
        drawer.settings["contrast"] = 50
        result = drawer.draw(make_ctx())
        # Uniform frame has no edges -> all values near 0 (after b/c adjust, near midpoint)
        # Edge detection output is 0 everywhere, contrast maps 0->~0, brightness adds 0
        # So result should be clustered near the palette midpoint
        unique_count = len(np.unique(result))
        assert unique_count < 10  # Very few unique values = no edges

    def test_edge_frame_has_edges(self):
        """A frame with a sharp boundary should produce edge output."""
        feed = FakeVideoFeed()
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[:, 160:, :] = 255  # Left half black, right half white
        feed.set_frame(frame)
        drawer = CameraDrawer(32, 18, video_feed=feed)
        drawer.settings["mode"] = CameraDrawer.MODE_EDGES
        result = drawer.draw(make_ctx())
        # Should have some high values at the edge boundary
        assert result.max() > 0


class TestCameraDrawerMotionMode:
    """Tests for motion-map mode."""

    def test_motion_mode_returns_correct_shape(self):
        feed = FakeVideoFeed()
        feed.set_frame(np.full((240, 320, 3), 128, dtype=np.uint8))
        motion_map = np.random.rand(240, 320).astype(np.float32)
        feed.set_motion_map(motion_map, amount=0.5)
        drawer = CameraDrawer(32, 18, video_feed=feed)
        drawer.settings["mode"] = CameraDrawer.MODE_MOTION
        result = drawer.draw(make_ctx())
        assert result.shape == (18, 32)

    def test_motion_mode_without_motion_map_falls_back(self):
        """If motion_map is None, should fall back to luminance."""
        feed = FakeVideoFeed()
        feed.set_frame(np.full((240, 320, 3), 200, dtype=np.uint8))
        # Don't set motion_map -> it stays None
        drawer = CameraDrawer(32, 18, video_feed=feed)
        drawer.settings["mode"] = CameraDrawer.MODE_MOTION
        result = drawer.draw(make_ctx())
        assert result.shape == (18, 32)
        assert np.all(result >= 0)
        assert np.all(result < 4096)

    def test_high_motion_produces_high_indices(self):
        feed = FakeVideoFeed()
        feed.set_frame(np.full((240, 320, 3), 128, dtype=np.uint8))
        motion_map = np.ones((240, 320), dtype=np.float32)  # Max motion everywhere
        feed.set_motion_map(motion_map, amount=1.0)
        drawer = CameraDrawer(32, 18, video_feed=feed)
        drawer.settings["mode"] = CameraDrawer.MODE_MOTION
        drawer.settings["brightness"] = 50
        drawer.settings["contrast"] = 50
        result = drawer.draw(make_ctx())
        assert np.mean(result) > 2000


class TestCameraDrawerSettings:
    """Tests for brightness, contrast, and mirror settings."""

    def test_high_brightness_increases_indices(self):
        feed = FakeVideoFeed()
        feed.set_frame(np.full((240, 320, 3), 128, dtype=np.uint8))
        drawer = CameraDrawer(32, 18, video_feed=feed)

        drawer.settings["brightness"] = 50
        drawer.settings["contrast"] = 50
        baseline = drawer.draw(make_ctx()).mean()

        drawer.settings["brightness"] = 90
        bright = drawer.draw(make_ctx()).mean()

        assert bright > baseline

    def test_low_brightness_decreases_indices(self):
        feed = FakeVideoFeed()
        feed.set_frame(np.full((240, 320, 3), 128, dtype=np.uint8))
        drawer = CameraDrawer(32, 18, video_feed=feed)

        drawer.settings["brightness"] = 50
        drawer.settings["contrast"] = 50
        baseline = drawer.draw(make_ctx()).mean()

        drawer.settings["brightness"] = 10
        dark = drawer.draw(make_ctx()).mean()

        assert dark < baseline

    def test_mirror_flips_horizontally(self):
        feed = FakeVideoFeed()
        # Create a frame with left=dark, right=bright
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[:, 160:, :] = 255
        feed.set_frame(frame)

        drawer = CameraDrawer(32, 18, video_feed=feed)
        drawer.settings["mirror"] = 0
        normal = drawer.draw(make_ctx())

        drawer.settings["mirror"] = 1
        mirrored = drawer.draw(make_ctx())

        # Mirrored frame should be flipped
        np.testing.assert_array_equal(mirrored, np.fliplr(normal))

    def test_set_video_feed(self):
        """set_video_feed() should replace the feed source."""
        drawer = CameraDrawer(32, 18)
        assert drawer.video_feed is None

        feed = FakeVideoFeed()
        feed.set_frame(np.full((240, 320, 3), 128, dtype=np.uint8))
        drawer.set_video_feed(feed)

        result = drawer.draw(make_ctx())
        # Should now work with the feed (not fallback)
        assert result.shape == (18, 32)

    def test_reset(self):
        drawer = CameraDrawer(32, 18)
        drawer._prev_frame = "something"
        drawer.reset()
        assert drawer._prev_frame is None

    def test_different_sizes(self):
        """CameraDrawer should work with different matrix dimensions."""
        feed = FakeVideoFeed()
        feed.set_frame(np.random.randint(0, 256, (240, 320, 3), dtype=np.uint8))
        for width, height in [(16, 16), (64, 32), (100, 50)]:
            drawer = CameraDrawer(width, height, video_feed=feed)
            ctx = make_ctx(width=width, height=height)
            result = drawer.draw(ctx)
            assert result.shape == (height, width)

    def test_update_settings_clamps(self):
        drawer = CameraDrawer(32, 18)
        drawer.update_settings({"brightness": 200})
        assert drawer.settings["brightness"] == 100
        drawer.update_settings({"brightness": -10})
        assert drawer.settings["brightness"] == 0
