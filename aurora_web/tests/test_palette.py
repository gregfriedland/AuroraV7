"""Tests for the Palette class."""

import numpy as np
import pytest

from aurora_web.core.palette import Palette, create_gradient_palette


class TestPalette:
    """Tests for Palette class."""

    def test_default_palette_size(self):
        """Default palette should have 4096 colors."""
        palette = Palette()
        assert palette.size == 4096
        assert palette.lut.shape == (4096, 3)

    def test_custom_size(self):
        """Palette should support custom sizes."""
        palette = Palette(size=256)
        assert palette.size == 256
        assert palette.lut.shape == (256, 3)

    def test_get_color(self):
        """get_color should return valid RGB tuple."""
        palette = Palette(size=256)
        color = palette.get_color(0)
        assert isinstance(color, tuple)
        assert len(color) == 3
        assert all(0 <= c <= 255 for c in color)

    def test_get_color_wraps(self):
        """get_color should wrap around palette size."""
        palette = Palette(size=256)
        # Index 256 should wrap to 0
        assert palette.get_color(256) == palette.get_color(0)
        assert palette.get_color(512) == palette.get_color(0)

    def test_indices_to_rgb_shape(self):
        """indices_to_rgb should return correct shape."""
        palette = Palette(size=256)
        indices = np.zeros((18, 32), dtype=np.int32)
        rgb = palette.indices_to_rgb(indices)
        assert rgb.shape == (18, 32, 3)
        assert rgb.dtype == np.uint8

    def test_indices_to_rgb_values(self):
        """indices_to_rgb should map indices to colors."""
        # Create simple 2-color gradient
        palette = Palette(size=2, base_colors=[(0, 0, 0), (255, 255, 255)])

        indices = np.array([[0, 1], [1, 0]], dtype=np.int32)
        rgb = palette.indices_to_rgb(indices)

        # Index 0 should be black (or close)
        assert rgb[0, 0, 0] < 128  # R
        # Index 1 should be white (or close)
        assert rgb[0, 1, 0] > 128  # R

    def test_indices_wrap(self):
        """indices_to_rgb should wrap indices to palette size."""
        palette = Palette(size=256)
        # Values > 255 should wrap
        indices = np.array([[256, 512]], dtype=np.int32)
        rgb = palette.indices_to_rgb(indices)
        # Should not raise and should return valid colors
        assert rgb.shape == (1, 2, 3)

    def test_set_base_colors(self):
        """set_base_colors should update the palette."""
        palette = Palette(size=256)
        original_first = palette.get_color(0)

        # Set new colors
        palette.set_base_colors([(0, 255, 0), (255, 0, 0)])
        new_first = palette.get_color(0)

        # First color should now be green
        assert new_first[1] > new_first[0]  # G > R

    def test_gradient_smooth(self):
        """Palette should create smooth gradients between colors."""
        palette = Palette(size=100, base_colors=[(0, 0, 0), (255, 255, 255)])

        # Get colors at 0%, 50%, 100%
        c0 = palette.get_color(0)
        c50 = palette.get_color(49)
        c100 = palette.get_color(99)

        # Should be monotonically increasing
        assert c0[0] < c50[0] < c100[0]


class TestCreateGradientPalette:
    """Tests for create_gradient_palette helper."""

    def test_creates_palette(self):
        """Should create a valid palette."""
        palette = create_gradient_palette((255, 0, 0), (0, 0, 255), size=100)
        assert isinstance(palette, Palette)
        assert palette.size == 100

    def test_gradient_colors(self):
        """Gradient should go from color1 to color2."""
        palette = create_gradient_palette((255, 0, 0), (0, 0, 255), size=100)

        # First color should be red
        first = palette.get_color(0)
        assert first[0] > 200  # High red
        assert first[2] < 50   # Low blue

        # Last color should be blue
        last = palette.get_color(99)
        assert last[0] < 50    # Low red
        assert last[2] > 200   # High blue
