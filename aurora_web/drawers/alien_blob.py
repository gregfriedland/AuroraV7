"""AlienBlob drawer - Perlin noise based flowing patterns."""

import numpy as np
from aurora_web.drawers.base import Drawer, DrawerContext


# Perlin noise implementation (Processing-style)
# Based on Processing's noise() function

PERLIN_YWRAPB = 4
PERLIN_YWRAP = 1 << PERLIN_YWRAPB
PERLIN_ZWRAPB = 8
PERLIN_ZWRAP = 1 << PERLIN_ZWRAPB
PERLIN_SIZE = 4095


class PerlinNoise:
    """Processing-style Perlin noise generator."""

    def __init__(self, seed: int = None):
        """Initialize noise generator.

        Args:
            seed: Random seed for reproducibility
        """
        if seed is not None:
            np.random.seed(seed)

        # Random permutation table
        self.perlin = np.random.random(PERLIN_SIZE + 1).astype(np.float32)

        # Precompute cosine table for interpolation
        self.perlin_cos_table = np.cos(np.arange(720) * np.pi / 360).astype(np.float32)
        self.perlin_pi = 360
        self.perlin_twopi = 720

    def _noise_fsc(self, i: float) -> float:
        """Fade/smoothing function using cosine interpolation."""
        idx = int(i * self.perlin_pi) % self.perlin_twopi
        return 0.5 * (1.0 - self.perlin_cos_table[idx])

    def noise(self, x: float, y: float, z: float, octaves: int = 4,
              falloff: float = 0.5) -> float:
        """Generate Perlin noise value.

        Args:
            x, y, z: Coordinates
            octaves: Number of noise layers
            falloff: Amplitude decay per octave

        Returns:
            Noise value in range [0, 1]
        """
        x = abs(x)
        y = abs(y)
        z = abs(z)

        xi, yi, zi = int(x), int(y), int(z)
        xf = x - xi
        yf = y - yi
        zf = z - zi

        r = 0.0
        ampl = 0.5

        for _ in range(octaves):
            of = xi + (yi << PERLIN_YWRAPB) + (zi << PERLIN_ZWRAPB)

            rxf = self._noise_fsc(xf)
            ryf = self._noise_fsc(yf)

            n1 = self.perlin[of & PERLIN_SIZE]
            n1 += rxf * (self.perlin[(of + 1) & PERLIN_SIZE] - n1)
            n2 = self.perlin[(of + PERLIN_YWRAP) & PERLIN_SIZE]
            n2 += rxf * (self.perlin[(of + PERLIN_YWRAP + 1) & PERLIN_SIZE] - n2)
            n1 += ryf * (n2 - n1)

            of += PERLIN_ZWRAP
            n2 = self.perlin[of & PERLIN_SIZE]
            n2 += rxf * (self.perlin[(of + 1) & PERLIN_SIZE] - n2)
            n3 = self.perlin[(of + PERLIN_YWRAP) & PERLIN_SIZE]
            n3 += rxf * (self.perlin[(of + PERLIN_YWRAP + 1) & PERLIN_SIZE] - n3)
            n2 += ryf * (n3 - n2)

            n1 += self._noise_fsc(zf) * (n2 - n1)

            r += n1 * ampl
            ampl *= falloff

            xi <<= 1
            xf *= 2
            yi <<= 1
            yf *= 2
            zi <<= 1
            zf *= 2

            if xf >= 1.0:
                xi += 1
                xf -= 1
            if yf >= 1.0:
                yi += 1
                yf -= 1
            if zf >= 1.0:
                zi += 1
                zf -= 1

        return r

    def _noise_fsc_vec(self, i: np.ndarray) -> np.ndarray:
        """Vectorized fade/smoothing function using cosine interpolation."""
        idx = (i * self.perlin_pi).astype(np.int32) % self.perlin_twopi
        return 0.5 * (1.0 - self.perlin_cos_table[idx])

    def noise_2d(self, x: np.ndarray, y: np.ndarray, z: float,
                 octaves: int = 4, falloff: float = 0.5) -> np.ndarray:
        """Fully vectorized 2D noise generation - no Python loops.

        Args:
            x, y: 2D coordinate arrays
            z: Z coordinate (typically time)
            octaves: Number of noise layers
            falloff: Amplitude decay per octave

        Returns:
            2D array of noise values
        """
        x = np.abs(x).astype(np.float32)
        y = np.abs(y).astype(np.float32)
        z = abs(z)

        # Precompute all octave coordinates at once: shape (octaves, height, width)
        # Each octave doubles the frequency
        scales = (2 ** np.arange(octaves)).astype(np.float32)  # [1, 2, 4, 8]
        ampls = (0.5 * falloff ** np.arange(octaves)).astype(np.float32)  # [0.5, 0.25, 0.125, 0.0625]

        # Broadcast to (octaves, height, width)
        x_scaled = x[np.newaxis, :, :] * scales[:, np.newaxis, np.newaxis]
        y_scaled = y[np.newaxis, :, :] * scales[:, np.newaxis, np.newaxis]
        z_scaled = z * scales  # (octaves,)

        # Integer and fractional parts
        xi = x_scaled.astype(np.int32)
        yi = y_scaled.astype(np.int32)
        zi = z_scaled.astype(np.int32)  # (octaves,)
        xf = x_scaled - xi
        yf = y_scaled - yi
        zf = z_scaled - zi  # (octaves,)

        # Compute offset indices: (octaves, height, width)
        of = xi + (yi << PERLIN_YWRAPB) + (zi[:, np.newaxis, np.newaxis] << PERLIN_ZWRAPB)

        # Smoothing functions
        rxf_idx = (xf * self.perlin_pi).astype(np.int32) % self.perlin_twopi
        ryf_idx = (yf * self.perlin_pi).astype(np.int32) % self.perlin_twopi
        rxf = 0.5 * (1.0 - self.perlin_cos_table[rxf_idx])
        ryf = 0.5 * (1.0 - self.perlin_cos_table[ryf_idx])

        # Z smoothing (one per octave)
        zf_idx = ((zf * self.perlin_pi).astype(np.int32) % self.perlin_twopi)
        rzf = 0.5 * (1.0 - self.perlin_cos_table[zf_idx])  # (octaves,)

        # Trilinear interpolation - all octaves at once
        n1 = self.perlin[of & PERLIN_SIZE]
        n1 = n1 + rxf * (self.perlin[(of + 1) & PERLIN_SIZE] - n1)
        n2 = self.perlin[(of + PERLIN_YWRAP) & PERLIN_SIZE]
        n2 = n2 + rxf * (self.perlin[(of + PERLIN_YWRAP + 1) & PERLIN_SIZE] - n2)
        n1 = n1 + ryf * (n2 - n1)

        of2 = of + PERLIN_ZWRAP
        n2 = self.perlin[of2 & PERLIN_SIZE]
        n2 = n2 + rxf * (self.perlin[(of2 + 1) & PERLIN_SIZE] - n2)
        n3 = self.perlin[(of2 + PERLIN_YWRAP) & PERLIN_SIZE]
        n3 = n3 + rxf * (self.perlin[(of2 + PERLIN_YWRAP + 1) & PERLIN_SIZE] - n3)
        n2 = n2 + ryf * (n3 - n2)

        # Z interpolation
        n1 = n1 + rzf[:, np.newaxis, np.newaxis] * (n2 - n1)

        # Sum all octaves with their amplitudes
        r = np.sum(n1 * ampls[:, np.newaxis, np.newaxis], axis=0)

        return r


class AlienBlobDrawer(Drawer):
    """Flowing, organic patterns using Perlin noise.

    Creates smooth, blob-like color patterns that flow and morph over time.
    """

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("AlienBlob", width, height, palette_size)

        # Settings
        self.settings = {
            "speed": 30,
            "colorSpeed": 0,
            "detail": 3,
            "zoom": 70,
        }
        self.settings_ranges = {
            "speed": (0, 100),
            "colorSpeed": (0, 50),
            "detail": (1, 4),
            "zoom": (0, 100),
        }

        # Noise generator
        self.noise_gen = PerlinNoise()

        # Precompute sine table
        self.sine_table = np.sin(np.arange(360) * np.pi / 180).astype(np.float32)

        # Create coordinate grids
        self._update_grids()

        # Animation state
        self.pos = 0.0
        self.color_index = 0

        self.reset()

    def _update_grids(self):
        """Precompute coordinate grids."""
        incr = 0.3125
        y_coords = np.arange(self.height) * incr
        x_coords = np.arange(self.width) * incr
        self.xx, self.yy = np.meshgrid(x_coords, y_coords)

    def reset(self) -> None:
        """Reset animation state."""
        self.pos = float(np.random.randint(0, 1000))
        self.color_index = 0
        self.noise_gen = PerlinNoise()  # New random noise

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        """Draw flowing noise pattern.

        Returns:
            Array of palette indices, shape (height, width)
        """
        # Get settings
        speed = self.settings["speed"]
        color_speed = self.settings["colorSpeed"]
        detail = self.settings["detail"]
        zoom = self.settings["zoom"]

        # Calculate zoom multiplier
        multiplier = (1 - zoom / 100.0) + 0.02

        # Scale coordinates
        xx_scaled = self.xx * multiplier
        yy_scaled = self.yy * multiplier

        # Generate noise values - fully vectorized
        noise_vals = self.noise_gen.noise_2d(
            xx_scaled, yy_scaled, self.pos,
            octaves=detail, falloff=0.5
        )

        # Map noise to angle (vectorized)
        noise_mult = 7.0
        deg = ((noise_vals * noise_mult + 4 * np.pi) * 180 / np.pi).astype(np.int32)
        h = (self.sine_table[deg % 360] + 1) / 2

        # Map to palette index
        indices = (h * self.palette_size).astype(np.int32)

        # Add color offset
        indices = (indices + self.color_index) % self.palette_size

        # Update animation state
        speed_mult = 0.07
        self.pos += speed_mult * speed / 100.0 * ctx.delta_time * 60
        self.color_index = (self.color_index + color_speed) % self.palette_size

        return indices
