"""Tests for the CanvasFeed class."""

import numpy as np
import pytest

from aurora_web.inputs.canvas_feed import CanvasFeed, Touch


class TestTouch:
    """Tests for Touch dataclass."""

    def test_default_values(self):
        """Touch should have sensible defaults."""
        touch = Touch(x=0.5, y=0.5)
        assert touch.x == 0.5
        assert touch.y == 0.5
        assert touch.pressure == 1.0
        assert touch.radius == 2.0
        assert touch.color == (255, 255, 255)

    def test_custom_values(self):
        """Touch should accept custom values."""
        touch = Touch(x=0.1, y=0.9, pressure=0.5, radius=5.0, color=(255, 0, 0))
        assert touch.x == 0.1
        assert touch.y == 0.9
        assert touch.pressure == 0.5
        assert touch.radius == 5.0
        assert touch.color == (255, 0, 0)


class TestCanvasFeed:
    """Tests for CanvasFeed class."""

    def test_initialization(self):
        """CanvasFeed should initialize with correct dimensions."""
        feed = CanvasFeed(32, 18)
        assert feed.width == 32
        assert feed.height == 18
        assert feed.paint_buffer.shape == (18, 32, 4)
        assert feed.touches == []
        assert feed.last_touch is None

    def test_paint_buffer_starts_empty(self):
        """Paint buffer should start all zeros (transparent black)."""
        feed = CanvasFeed(32, 18)
        assert np.all(feed.paint_buffer == 0)

    def test_set_color(self):
        """set_color should update current color."""
        feed = CanvasFeed(32, 18)
        feed.set_color(255, 0, 0)
        assert feed._current_color == (255, 0, 0)

    def test_set_radius(self):
        """set_radius should update brush size."""
        feed = CanvasFeed(32, 18)
        feed.set_radius(5.0)
        assert feed._current_radius == 5.0

    def test_set_radius_minimum(self):
        """set_radius should enforce minimum of 1."""
        feed = CanvasFeed(32, 18)
        feed.set_radius(0.5)
        assert feed._current_radius == 1.0

    def test_touch_start_adds_touch(self):
        """touch_start should add a touch and paint."""
        feed = CanvasFeed(32, 18)
        feed.touch_start(0.5, 0.5, color=(255, 0, 0), radius=2)

        assert len(feed.touches) == 1
        assert feed.last_touch is not None
        assert feed.last_touch.color == (255, 0, 0)
        # Should have painted something
        assert feed.has_paint()

    def test_touch_move_draws_line(self):
        """touch_move should draw from last position."""
        feed = CanvasFeed(32, 18)
        feed.touch_start(0.1, 0.1, color=(0, 255, 0), radius=1)
        feed.touch_move(0.9, 0.9)

        # Should have paint along the line
        assert feed.has_paint()
        # Last position should be updated
        assert feed.touches[-1].x == 0.9
        assert feed.touches[-1].y == 0.9

    def test_touch_end_removes_touch(self):
        """touch_end should remove the active touch."""
        feed = CanvasFeed(32, 18)
        feed.touch_start(0.5, 0.5)
        assert len(feed.touches) == 1
        feed.touch_end()
        assert len(feed.touches) == 0

    def test_touch_end_when_empty(self):
        """touch_end should not error when no touches."""
        feed = CanvasFeed(32, 18)
        feed.touch_end()  # Should not raise
        assert len(feed.touches) == 0

    def test_clear(self):
        """clear should reset paint buffer."""
        feed = CanvasFeed(32, 18)
        feed.touch_start(0.5, 0.5, color=(255, 0, 0), radius=5)
        assert feed.has_paint()
        feed.clear()
        assert not feed.has_paint()
        assert np.all(feed.paint_buffer == 0)

    def test_decay(self):
        """update with decay should fade paint."""
        feed = CanvasFeed(32, 18)
        feed.touch_start(0.5, 0.5, color=(255, 255, 255), radius=3)
        feed.touch_end()

        # Set decay rate
        feed.set_decay(10.0)  # Fast decay for testing

        # Get initial alpha
        initial_alpha = feed.paint_buffer[:, :, 3].max()
        assert initial_alpha > 0

        # Update with 0.1 seconds
        feed.update(0.1)

        # Alpha should have decreased
        new_alpha = feed.paint_buffer[:, :, 3].max()
        assert new_alpha < initial_alpha

    def test_no_decay_when_zero(self):
        """update should not decay when rate is 0."""
        feed = CanvasFeed(32, 18)
        feed.touch_start(0.5, 0.5, color=(255, 255, 255), radius=3)
        feed.touch_end()

        feed.set_decay(0.0)  # No decay
        initial_alpha = feed.paint_buffer[:, :, 3].max()

        feed.update(1.0)  # 1 second

        new_alpha = feed.paint_buffer[:, :, 3].max()
        assert new_alpha == initial_alpha

    def test_get_rgb_frame(self):
        """get_rgb_frame should return RGB array."""
        feed = CanvasFeed(32, 18)
        feed.touch_start(0.5, 0.5, color=(255, 0, 0), radius=2)

        rgb = feed.get_rgb_frame()
        assert rgb.shape == (18, 32, 3)
        assert rgb.dtype == np.uint8

        # Should have some red pixels
        assert np.any(rgb[:, :, 0] > 0)

    def test_has_paint(self):
        """has_paint should correctly detect paint."""
        feed = CanvasFeed(32, 18)
        assert not feed.has_paint()

        feed.touch_start(0.5, 0.5)
        assert feed.has_paint()

        feed.clear()
        assert not feed.has_paint()

    def test_paint_circle_bounds(self):
        """Paint should be clipped to canvas bounds."""
        feed = CanvasFeed(32, 18)
        # Paint at corner with large radius
        feed.touch_start(0.0, 0.0, radius=10)

        # Should not raise IndexError and should have some paint
        assert feed.has_paint()

        # Paint at opposite corner
        feed.touch_start(1.0, 1.0, radius=10)
        assert feed.has_paint()

    def test_multiple_colors(self):
        """Multiple colors should coexist on canvas."""
        feed = CanvasFeed(32, 18)

        # Paint red on left
        feed.touch_start(0.25, 0.5, color=(255, 0, 0), radius=3)
        feed.touch_end()

        # Paint blue on right
        feed.touch_start(0.75, 0.5, color=(0, 0, 255), radius=3)
        feed.touch_end()

        rgb = feed.get_rgb_frame()

        # Left side should have red
        left_half = rgb[:, :16, :]
        assert np.any(left_half[:, :, 0] > 100)  # Red channel

        # Right side should have blue
        right_half = rgb[:, 16:, :]
        assert np.any(right_half[:, :, 2] > 100)  # Blue channel
