"""Tests for CustomDrawer and CustomDrawerLoader."""

import numpy as np
import pytest
import tempfile
from pathlib import Path

from aurora_web.drawers.custom import CustomDrawer, CustomDrawerLoader, EXAMPLE_DRAWER_YAML
from aurora_web.drawers.base import DrawerContext


class TestCustomDrawer:
    """Tests for CustomDrawer class."""

    def test_load_from_yaml_string(self):
        """CustomDrawer should load from YAML string."""
        drawer = CustomDrawer.from_yaml_string(
            EXAMPLE_DRAWER_YAML,
            width=32,
            height=18,
        )
        assert drawer.name == "Wave Pattern"
        assert drawer.author == "example"
        assert drawer.width == 32
        assert drawer.height == 18

    def test_parse_settings(self):
        """CustomDrawer should parse settings from YAML."""
        drawer = CustomDrawer.from_yaml_string(
            EXAMPLE_DRAWER_YAML,
            width=32,
            height=18,
        )
        assert "speed" in drawer.settings
        assert "wave_count" in drawer.settings
        assert "color_speed" in drawer.settings
        assert drawer.settings["speed"] == 1.0
        assert drawer.settings["wave_count"] == 3

    def test_settings_ranges(self):
        """Settings should have proper ranges."""
        drawer = CustomDrawer.from_yaml_string(
            EXAMPLE_DRAWER_YAML,
            width=32,
            height=18,
        )
        assert "speed" in drawer.settings_ranges
        assert drawer.settings_ranges["speed"] == (0.1, 5.0)
        assert drawer.settings_ranges["wave_count"] == (1, 10)

    def test_draw_returns_correct_shape(self):
        """draw() should return array of correct shape."""
        drawer = CustomDrawer.from_yaml_string(
            EXAMPLE_DRAWER_YAML,
            width=32,
            height=18,
        )
        ctx = DrawerContext(
            width=32,
            height=18,
            frame_num=0,
            time=0.0,
            delta_time=0.016,
        )
        result = drawer.draw(ctx)
        assert result.shape == (18, 32)
        assert result.dtype == np.int32

    def test_draw_returns_valid_indices(self):
        """draw() should return valid palette indices."""
        drawer = CustomDrawer.from_yaml_string(
            EXAMPLE_DRAWER_YAML,
            width=32,
            height=18,
            palette_size=4096,
        )
        ctx = DrawerContext(
            width=32,
            height=18,
            frame_num=0,
            time=0.0,
            delta_time=0.016,
        )
        result = drawer.draw(ctx)
        assert np.all(result >= 0)
        assert np.all(result < 4096)

    def test_draw_produces_animation(self):
        """draw() should produce different results over time."""
        drawer = CustomDrawer.from_yaml_string(
            EXAMPLE_DRAWER_YAML,
            width=32,
            height=18,
        )
        ctx1 = DrawerContext(width=32, height=18, frame_num=0, time=0.0, delta_time=0.016)
        ctx2 = DrawerContext(width=32, height=18, frame_num=10, time=0.5, delta_time=0.016)

        result1 = drawer.draw(ctx1)
        result2 = drawer.draw(ctx2)

        # Results should be different due to time-based animation
        assert not np.array_equal(result1, result2)

    def test_update_settings(self):
        """update_settings() should update drawer settings."""
        drawer = CustomDrawer.from_yaml_string(
            EXAMPLE_DRAWER_YAML,
            width=32,
            height=18,
        )
        drawer.update_settings({"speed": 3.0, "wave_count": 5})
        assert drawer.settings["speed"] == 3.0
        assert drawer.settings["wave_count"] == 5

    def test_invalid_code_raises(self):
        """Invalid code should raise ValueError."""
        bad_yaml = """
name: "Bad Drawer"
code: |
  def draw_wrong_name(width, height, ctx, settings, palette_size):
      return np.zeros((height, width), dtype=np.int32)
"""
        with pytest.raises(ValueError, match="must define a 'draw' function"):
            CustomDrawer.from_yaml_string(bad_yaml, width=32, height=18)

    def test_syntax_error_raises(self):
        """Syntax error in code should raise ValueError."""
        bad_yaml = """
name: "Syntax Error"
code: |
  def draw(width, height, ctx, settings, palette_size):
      return this is not valid python
"""
        with pytest.raises(ValueError, match="Failed to compile"):
            CustomDrawer.from_yaml_string(bad_yaml, width=32, height=18)

    def test_uses_flags(self):
        """uses flags should be parsed correctly."""
        yaml_content = """
name: "Test Uses"
uses:
  audio: true
  video: false
  canvas: true
code: |
  def draw(width, height, ctx, settings, palette_size):
      return np.zeros((height, width), dtype=np.int32)
"""
        drawer = CustomDrawer.from_yaml_string(yaml_content, width=32, height=18)
        assert drawer.uses_audio is True
        assert drawer.uses_video is False
        assert drawer.uses_canvas is True

    def test_to_yaml(self):
        """to_yaml() should return YAML representation."""
        drawer = CustomDrawer.from_yaml_string(
            EXAMPLE_DRAWER_YAML,
            width=32,
            height=18,
        )
        yaml_str = drawer.to_yaml()
        assert "name: Wave Pattern" in yaml_str or "name: 'Wave Pattern'" in yaml_str

    def test_reset_clears_state(self):
        """reset() should clear internal state."""
        drawer = CustomDrawer.from_yaml_string(
            EXAMPLE_DRAWER_YAML,
            width=32,
            height=18,
        )
        drawer._state["test"] = "value"
        drawer.reset()
        assert drawer._state == {}


class TestCustomDrawerLoader:
    """Tests for CustomDrawerLoader class."""

    def test_initialization(self):
        """CustomDrawerLoader should initialize with path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CustomDrawerLoader(
                Path(tmpdir),
                width=32,
                height=18,
            )
            assert loader.base_path.exists()

    def test_list_drawers_empty(self):
        """list_drawers() should return empty list for empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CustomDrawerLoader(Path(tmpdir), width=32, height=18)
            drawers = loader.list_drawers()
            assert drawers == []

    def test_save_and_load_drawer(self):
        """save_drawer() and load_drawer() should work together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CustomDrawerLoader(Path(tmpdir), width=32, height=18)

            definition = {
                'name': 'Test Drawer',
                'description': 'A test drawer',
                'uses': {'audio': False, 'video': False, 'canvas': False},
                'settings': {'speed': {'type': 'float', 'default': 1.0, 'min': 0.1, 'max': 5.0}},
                'code': '''def draw(width, height, ctx, settings, palette_size):
    return np.zeros((height, width), dtype=np.int32)
''',
            }

            # Save drawer
            rel_path = loader.save_drawer("testuser", "Test Drawer", definition)
            assert rel_path == "testuser/Test_Drawer.yaml"

            # Load drawer
            drawer = loader.load_drawer(rel_path)
            assert drawer.name == "Test Drawer"
            assert drawer.author == "testuser"

    def test_list_drawers_returns_saved(self):
        """list_drawers() should return saved drawers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CustomDrawerLoader(Path(tmpdir), width=32, height=18)

            definition = {
                'name': 'Test Drawer',
                'description': 'Description',
                'code': '''def draw(width, height, ctx, settings, palette_size):
    return np.zeros((height, width), dtype=np.int32)
''',
            }

            loader.save_drawer("testuser", "Test Drawer", definition)
            drawers = loader.list_drawers()

            assert len(drawers) == 1
            assert drawers[0]['name'] == "Test Drawer"
            assert drawers[0]['author'] == "testuser"

    def test_list_drawers_by_user(self):
        """list_drawers() should filter by username."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CustomDrawerLoader(Path(tmpdir), width=32, height=18)

            definition = {
                'name': 'Drawer',
                'code': '''def draw(width, height, ctx, settings, palette_size):
    return np.zeros((height, width), dtype=np.int32)
''',
            }

            loader.save_drawer("user1", "Drawer1", definition)
            loader.save_drawer("user2", "Drawer2", definition)

            user1_drawers = loader.list_drawers("user1")
            user2_drawers = loader.list_drawers("user2")
            all_drawers = loader.list_drawers()

            assert len(user1_drawers) == 1
            assert len(user2_drawers) == 1
            assert len(all_drawers) == 2

    def test_delete_drawer(self):
        """delete_drawer() should remove drawer file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CustomDrawerLoader(Path(tmpdir), width=32, height=18)

            definition = {
                'name': 'To Delete',
                'code': '''def draw(width, height, ctx, settings, palette_size):
    return np.zeros((height, width), dtype=np.int32)
''',
            }

            rel_path = loader.save_drawer("testuser", "To Delete", definition)
            assert loader.delete_drawer(rel_path) is True
            assert loader.list_drawers() == []

    def test_delete_nonexistent_drawer(self):
        """delete_drawer() should return False for nonexistent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CustomDrawerLoader(Path(tmpdir), width=32, height=18)
            assert loader.delete_drawer("nonexistent/drawer.yaml") is False


class TestCustomDrawerExamples:
    """Tests for the example custom drawers."""

    def test_load_wave_pattern(self):
        """Wave pattern example should load and draw."""
        example_path = Path(__file__).parent.parent / "custom_drawers" / "example" / "wave_pattern.yaml"
        if not example_path.exists():
            pytest.skip("Example drawer not found")

        drawer = CustomDrawer(
            width=32,
            height=18,
            yaml_path=example_path,
        )
        ctx = DrawerContext(width=32, height=18, frame_num=0, time=0.0, delta_time=0.016)
        result = drawer.draw(ctx)

        assert result.shape == (18, 32)
        assert np.all(result >= 0)

    def test_load_plasma(self):
        """Plasma example should load and draw."""
        example_path = Path(__file__).parent.parent / "custom_drawers" / "example" / "plasma.yaml"
        if not example_path.exists():
            pytest.skip("Example drawer not found")

        drawer = CustomDrawer(
            width=32,
            height=18,
            yaml_path=example_path,
        )
        ctx = DrawerContext(width=32, height=18, frame_num=0, time=0.0, delta_time=0.016)
        result = drawer.draw(ctx)

        assert result.shape == (18, 32)
        assert np.all(result >= 0)
