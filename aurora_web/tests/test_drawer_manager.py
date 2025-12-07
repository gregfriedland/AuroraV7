"""Tests for DrawerManager class."""

import numpy as np
import pytest

from aurora_web.core.drawer_manager import DrawerManager
from aurora_web.drawers.off import OffDrawer
from aurora_web.drawers.alien_blob import AlienBlobDrawer


class TestDrawerManager:
    """Tests for DrawerManager class."""

    def test_initialization(self):
        """DrawerManager should initialize with correct dimensions."""
        manager = DrawerManager(32, 18)
        assert manager.width == 32
        assert manager.height == 18
        assert manager.palette_size == 4096
        assert manager.mode == "paint"
        assert manager.active_drawer is None

    def test_register_drawer(self):
        """register_drawer should add drawer to registry."""
        manager = DrawerManager(32, 18)
        drawer = OffDrawer(32, 18)
        manager.register_drawer(drawer)
        assert "Off" in manager.drawers
        assert manager.drawers["Off"] is drawer

    def test_register_multiple_drawers(self):
        """Multiple drawers can be registered."""
        manager = DrawerManager(32, 18)
        manager.register_drawer(OffDrawer(32, 18))
        manager.register_drawer(AlienBlobDrawer(32, 18))
        assert len(manager.drawers) == 2
        assert "Off" in manager.drawers
        assert "AlienBlob" in manager.drawers

    def test_get_drawer_list(self):
        """get_drawer_list should return drawer info."""
        manager = DrawerManager(32, 18)
        manager.register_drawer(OffDrawer(32, 18))
        drawers = manager.get_drawer_list()
        assert len(drawers) == 1
        assert drawers[0]["name"] == "Off"
        assert "settings" in drawers[0]

    def test_set_mode_valid(self):
        """set_mode should accept valid modes."""
        manager = DrawerManager(32, 18)
        assert manager.set_mode("paint") is True
        assert manager.mode == "paint"
        assert manager.set_mode("pattern") is True
        assert manager.mode == "pattern"

    def test_set_mode_invalid(self):
        """set_mode should reject invalid modes."""
        manager = DrawerManager(32, 18)
        assert manager.set_mode("invalid") is False
        assert manager.mode == "paint"  # Unchanged

    def test_set_active_drawer(self):
        """set_active_drawer should activate drawer by name."""
        manager = DrawerManager(32, 18)
        drawer = OffDrawer(32, 18)
        manager.register_drawer(drawer)

        assert manager.set_active_drawer("Off") is True
        assert manager.active_drawer is drawer

    def test_set_active_drawer_not_found(self):
        """set_active_drawer should return False for unknown drawer."""
        manager = DrawerManager(32, 18)
        assert manager.set_active_drawer("Unknown") is False
        assert manager.active_drawer is None

    def test_set_active_drawer_resets_drawer(self):
        """set_active_drawer should reset the drawer."""
        manager = DrawerManager(32, 18)
        drawer = OffDrawer(32, 18)
        drawer.pos = 100.0  # Modify state
        manager.register_drawer(drawer)

        manager.set_active_drawer("Off")
        assert drawer.pos == 0.0  # Should be reset

    def test_update_drawer_settings(self):
        """update_drawer_settings should update active drawer."""
        manager = DrawerManager(32, 18)
        drawer = OffDrawer(32, 18)
        manager.register_drawer(drawer)
        manager.set_active_drawer("Off")

        assert manager.update_drawer_settings({"speed": 15}) is True
        assert drawer.settings["speed"] == 15

    def test_update_drawer_settings_no_active(self):
        """update_drawer_settings should return False with no active drawer."""
        manager = DrawerManager(32, 18)
        assert manager.update_drawer_settings({"speed": 15}) is False

    def test_set_palette_colors(self):
        """set_palette_colors should update palette."""
        manager = DrawerManager(32, 18)
        manager.set_palette_colors([(255, 0, 0), (0, 0, 255)])
        # First color should be red-ish
        color = manager.palette.get_color(0)
        assert color[0] > color[2]  # More red than blue

    def test_get_frame_paint_mode_with_frame(self):
        """get_frame in paint mode should return browser frame."""
        manager = DrawerManager(32, 18)
        manager.set_mode("paint")

        browser_frame = np.full((18, 32, 3), 128, dtype=np.uint8)
        result = manager.get_frame(browser_frame)

        np.testing.assert_array_equal(result, browser_frame)

    def test_get_frame_paint_mode_no_frame(self):
        """get_frame in paint mode without frame should return black."""
        manager = DrawerManager(32, 18)
        manager.set_mode("paint")

        result = manager.get_frame(None)
        assert result.shape == (18, 32, 3)
        assert np.all(result == 0)

    def test_get_frame_pattern_mode(self):
        """get_frame in pattern mode should generate from drawer."""
        manager = DrawerManager(32, 18)
        manager.register_drawer(OffDrawer(32, 18))
        manager.set_active_drawer("Off")
        manager.set_mode("pattern")

        result = manager.get_frame(None)
        assert result.shape == (18, 32, 3)
        assert result.dtype == np.uint8
        # Should have some non-black pixels (color ramp)
        assert np.any(result > 0)

    def test_get_frame_pattern_mode_no_drawer(self):
        """get_frame in pattern mode without drawer should return black."""
        manager = DrawerManager(32, 18)
        manager.set_mode("pattern")

        result = manager.get_frame(None)
        assert np.all(result == 0)

    def test_get_frame_increments_frame_num(self):
        """get_frame should increment frame number."""
        manager = DrawerManager(32, 18)
        initial_frame = manager.frame_num

        manager.get_frame(None)
        assert manager.frame_num == initial_frame + 1

        manager.get_frame(None)
        assert manager.frame_num == initial_frame + 2

    def test_get_status(self):
        """get_status should return current state."""
        manager = DrawerManager(32, 18)
        manager.register_drawer(OffDrawer(32, 18))
        manager.set_active_drawer("Off")
        manager.set_mode("pattern")

        status = manager.get_status()
        assert status["mode"] == "pattern"
        assert status["active_drawer"] == "Off"
        assert "Off" in status["drawers"]

    def test_get_status_no_active_drawer(self):
        """get_status should handle no active drawer."""
        manager = DrawerManager(32, 18)
        status = manager.get_status()
        assert status["active_drawer"] is None

    def test_black_frame_correct_shape(self):
        """black_frame should have correct shape and be all zeros."""
        manager = DrawerManager(64, 32)
        assert manager.black_frame.shape == (32, 64, 3)
        assert np.all(manager.black_frame == 0)

    def test_custom_palette_size(self):
        """DrawerManager should accept custom palette size."""
        manager = DrawerManager(32, 18, palette_size=256)
        assert manager.palette_size == 256
        assert manager.palette.size == 256
