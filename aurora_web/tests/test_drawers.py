"""Tests for drawer classes."""

import numpy as np
import pytest

from aurora_web.drawers.base import Drawer, DrawerContext
from aurora_web.drawers.off import OffDrawer
from aurora_web.drawers.alien_blob import AlienBlobDrawer, PerlinNoise
from aurora_web.drawers.bzr import BzrDrawer
from aurora_web.drawers.gray_scott import GrayScottDrawer
from aurora_web.drawers.ginzburg_landau import GinzburgLandauDrawer


class TestDrawerContext:
    """Tests for DrawerContext dataclass."""

    def test_default_values(self):
        """DrawerContext should have sensible defaults."""
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016
        )
        assert ctx.width == 32
        assert ctx.height == 18
        assert ctx.palette_size == 4096

    def test_custom_palette_size(self):
        """DrawerContext should accept custom palette size."""
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016,
            palette_size=256
        )
        assert ctx.palette_size == 256


class TestOffDrawer:
    """Tests for OffDrawer class."""

    def test_initialization(self):
        """OffDrawer should initialize correctly."""
        drawer = OffDrawer(32, 18)
        assert drawer.name == "Off"
        assert drawer.width == 32
        assert drawer.height == 18
        assert drawer.palette_size == 4096

    def test_has_settings(self):
        """OffDrawer should have speed setting."""
        drawer = OffDrawer(32, 18)
        assert "speed" in drawer.settings
        assert "speed" in drawer.settings_ranges

    def test_draw_returns_correct_shape(self):
        """draw() should return array of correct shape."""
        drawer = OffDrawer(32, 18)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016
        )
        result = drawer.draw(ctx)
        assert result.shape == (18, 32)
        assert result.dtype == np.int32

    def test_draw_returns_valid_indices(self):
        """draw() should return valid palette indices."""
        drawer = OffDrawer(32, 18, palette_size=4096)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016
        )
        result = drawer.draw(ctx)
        assert np.all(result >= 0)
        assert np.all(result < 4096)

    def test_reset_resets_position(self):
        """reset() should reset animation position."""
        drawer = OffDrawer(32, 18)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.1
        )
        # Draw a few frames to advance position
        drawer.draw(ctx)
        drawer.draw(ctx)
        assert drawer.pos != 0.0

        drawer.reset()
        assert drawer.pos == 0.0

    def test_update_settings(self):
        """update_settings() should update speed."""
        drawer = OffDrawer(32, 18)
        drawer.update_settings({"speed": 10})
        assert drawer.settings["speed"] == 10

    def test_update_settings_clamps_values(self):
        """update_settings() should clamp to valid range."""
        drawer = OffDrawer(32, 18)
        drawer.update_settings({"speed": 100})  # Above max of 20
        assert drawer.settings["speed"] == 20

        drawer.update_settings({"speed": 0})  # Below min of 1
        assert drawer.settings["speed"] == 1

    def test_get_settings_info(self):
        """get_settings_info() should return settings with ranges."""
        drawer = OffDrawer(32, 18)
        info = drawer.get_settings_info()
        assert "speed" in info
        assert "value" in info["speed"]
        assert "min" in info["speed"]
        assert "max" in info["speed"]

    def test_randomize_settings(self):
        """randomize_settings() should set random values within range."""
        drawer = OffDrawer(32, 18)
        original_speed = drawer.settings["speed"]

        # Run multiple times to ensure randomization works
        np.random.seed(42)
        drawer.randomize_settings()

        # Value should be within range
        assert 1 <= drawer.settings["speed"] <= 20


class TestPerlinNoise:
    """Tests for PerlinNoise class."""

    def test_initialization(self):
        """PerlinNoise should initialize with random permutation."""
        noise = PerlinNoise()
        assert noise.perlin.shape == (4096,)
        assert noise.perlin.dtype == np.float32

    def test_seeded_initialization(self):
        """PerlinNoise with same seed should produce same values."""
        noise1 = PerlinNoise(seed=42)
        noise2 = PerlinNoise(seed=42)
        np.testing.assert_array_equal(noise1.perlin, noise2.perlin)

    def test_noise_returns_float(self):
        """noise() should return a float value."""
        noise = PerlinNoise(seed=42)
        result = noise.noise(0.5, 0.5, 0.5)
        assert isinstance(result, float)

    def test_noise_in_range(self):
        """noise() should return values in [0, 1] range."""
        noise = PerlinNoise(seed=42)
        for x in np.linspace(0, 10, 20):
            for y in np.linspace(0, 10, 20):
                result = noise.noise(x, y, 0.0)
                assert 0 <= result <= 1

    def test_noise_is_smooth(self):
        """noise() should return similar values for nearby coordinates."""
        noise = PerlinNoise(seed=42)
        v1 = noise.noise(1.0, 1.0, 0.0)
        v2 = noise.noise(1.01, 1.01, 0.0)
        # Nearby points should have similar values
        assert abs(v1 - v2) < 0.1

    def test_noise_2d(self):
        """noise_2d() should return 2D array of noise values."""
        noise = PerlinNoise(seed=42)
        x = np.arange(4).reshape(2, 2).astype(np.float32) * 0.1
        y = np.arange(4).reshape(2, 2).astype(np.float32) * 0.1
        result = noise.noise_2d(x, y, 0.0)
        assert result.shape == (2, 2)
        assert result.dtype == np.float32


class TestAlienBlobDrawer:
    """Tests for AlienBlobDrawer class."""

    def test_initialization(self):
        """AlienBlobDrawer should initialize correctly."""
        drawer = AlienBlobDrawer(32, 18)
        assert drawer.name == "AlienBlob"
        assert drawer.width == 32
        assert drawer.height == 18

    def test_has_settings(self):
        """AlienBlobDrawer should have expected settings."""
        drawer = AlienBlobDrawer(32, 18)
        assert "speed" in drawer.settings
        assert "colorSpeed" in drawer.settings
        assert "detail" in drawer.settings
        assert "zoom" in drawer.settings

    def test_draw_returns_correct_shape(self):
        """draw() should return array of correct shape."""
        drawer = AlienBlobDrawer(32, 18)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016
        )
        result = drawer.draw(ctx)
        assert result.shape == (18, 32)
        assert result.dtype == np.int32

    def test_draw_returns_valid_indices(self):
        """draw() should return valid palette indices."""
        drawer = AlienBlobDrawer(32, 18, palette_size=4096)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016
        )
        result = drawer.draw(ctx)
        assert np.all(result >= 0)
        assert np.all(result < 4096)

    def test_reset_creates_new_noise(self):
        """reset() should create new noise generator."""
        drawer = AlienBlobDrawer(32, 18)
        old_perlin = drawer.noise_gen.perlin.copy()
        drawer.reset()
        # New random noise should be different
        assert not np.array_equal(old_perlin, drawer.noise_gen.perlin)

    def test_animation_advances(self):
        """Drawing frames should advance animation state."""
        drawer = AlienBlobDrawer(32, 18)
        drawer.reset()
        initial_pos = drawer.pos

        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.1
        )
        drawer.draw(ctx)

        assert drawer.pos != initial_pos

    def test_different_sizes(self):
        """AlienBlobDrawer should work with different dimensions."""
        for width, height in [(16, 16), (64, 32), (100, 50)]:
            drawer = AlienBlobDrawer(width, height)
            ctx = DrawerContext(
                width=width, height=height, frame_num=0, time=0.0, delta_time=0.016
            )
            result = drawer.draw(ctx)
            assert result.shape == (height, width)


class TestBzrDrawer:
    """Tests for BzrDrawer class."""

    def test_initialization(self):
        """BzrDrawer should initialize correctly."""
        drawer = BzrDrawer(32, 18)
        assert drawer.name == "Bzr"
        assert drawer.width == 32
        assert drawer.height == 18

    def test_has_settings(self):
        """BzrDrawer should have expected settings."""
        drawer = BzrDrawer(32, 18)
        assert "speed" in drawer.settings
        assert "colorSpeed" in drawer.settings
        assert "zoom" in drawer.settings
        assert "params" in drawer.settings

    def test_draw_returns_correct_shape(self):
        """draw() should return array of correct shape."""
        drawer = BzrDrawer(32, 18)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016
        )
        result = drawer.draw(ctx)
        assert result.shape == (18, 32)
        assert result.dtype == np.int32

    def test_draw_returns_valid_indices(self):
        """draw() should return valid palette indices."""
        drawer = BzrDrawer(32, 18, palette_size=4096)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016
        )
        result = drawer.draw(ctx)
        assert np.all(result >= 0)
        assert np.all(result < 4096)

    def test_reset_initializes_arrays(self):
        """reset() should initialize concentration arrays."""
        drawer = BzrDrawer(32, 18)
        drawer.reset()
        assert drawer.a[0] is not None
        assert drawer.b[0] is not None
        assert drawer.c[0] is not None
        assert drawer.a[0].shape == (drawer.bzr_height, drawer.bzr_width)

    def test_simulation_evolves(self):
        """Simulation should change state over time."""
        drawer = BzrDrawer(32, 18)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.1
        )

        # Get initial state
        initial_a = drawer.a[drawer.q].copy()

        # Draw several frames to advance simulation
        for _ in range(10):
            drawer.draw(ctx)

        # State should have changed
        assert not np.allclose(initial_a, drawer.a[drawer.q])


class TestGrayScottDrawer:
    """Tests for GrayScottDrawer class."""

    def test_initialization(self):
        """GrayScottDrawer should initialize correctly."""
        drawer = GrayScottDrawer(32, 18)
        assert drawer.name == "GrayScott"
        assert drawer.width == 32
        assert drawer.height == 18

    def test_has_settings(self):
        """GrayScottDrawer should have expected settings."""
        drawer = GrayScottDrawer(32, 18)
        assert "speed" in drawer.settings
        assert "colorSpeed" in drawer.settings
        assert "params" in drawer.settings

    def test_draw_returns_correct_shape(self):
        """draw() should return array of correct shape."""
        drawer = GrayScottDrawer(32, 18)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016
        )
        result = drawer.draw(ctx)
        assert result.shape == (18, 32)
        assert result.dtype == np.int32

    def test_draw_returns_valid_indices(self):
        """draw() should return valid palette indices."""
        drawer = GrayScottDrawer(32, 18, palette_size=4096)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016
        )
        result = drawer.draw(ctx)
        assert np.all(result >= 0)
        assert np.all(result < 4096)

    def test_reset_initializes_uv(self):
        """reset() should initialize U and V arrays."""
        drawer = GrayScottDrawer(32, 18)
        drawer.reset()
        assert drawer.u[0] is not None
        assert drawer.v[0] is not None
        assert drawer.u[0].shape == (18, 32)
        assert drawer.v[0].shape == (18, 32)

    def test_simulation_evolves(self):
        """Simulation should change state over time."""
        drawer = GrayScottDrawer(32, 18)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.1
        )

        # Get initial state
        initial_v = drawer.v[drawer.q].copy()

        # Draw several frames
        for _ in range(5):
            drawer.draw(ctx)

        # State should have changed
        assert not np.allclose(initial_v, drawer.v[drawer.q])


class TestGinzburgLandauDrawer:
    """Tests for GinzburgLandauDrawer class."""

    def test_initialization(self):
        """GinzburgLandauDrawer should initialize correctly."""
        drawer = GinzburgLandauDrawer(32, 18)
        assert drawer.name == "GinzburgLandau"
        assert drawer.width == 32
        assert drawer.height == 18

    def test_has_settings(self):
        """GinzburgLandauDrawer should have expected settings."""
        drawer = GinzburgLandauDrawer(32, 18)
        assert "speed" in drawer.settings
        assert "colorSpeed" in drawer.settings
        assert "params" in drawer.settings

    def test_draw_returns_correct_shape(self):
        """draw() should return array of correct shape."""
        drawer = GinzburgLandauDrawer(32, 18)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016
        )
        result = drawer.draw(ctx)
        assert result.shape == (18, 32)
        assert result.dtype == np.int32

    def test_draw_returns_valid_indices(self):
        """draw() should return valid palette indices."""
        drawer = GinzburgLandauDrawer(32, 18, palette_size=4096)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.016
        )
        result = drawer.draw(ctx)
        assert np.all(result >= 0)
        assert np.all(result < 4096)

    def test_reset_initializes_uv(self):
        """reset() should initialize U and V arrays."""
        drawer = GinzburgLandauDrawer(32, 18)
        drawer.reset()
        assert drawer.u[0] is not None
        assert drawer.v[0] is not None
        assert drawer.u[0].shape == (18, 32)

    def test_simulation_evolves(self):
        """Simulation should change state over time."""
        drawer = GinzburgLandauDrawer(32, 18)
        ctx = DrawerContext(
            width=32, height=18, frame_num=0, time=0.0, delta_time=0.1
        )

        # Get initial state
        initial_u = drawer.u[drawer.q].copy()

        # Draw several frames
        for _ in range(5):
            drawer.draw(ctx)

        # State should have changed
        assert not np.allclose(initial_u, drawer.u[drawer.q])
