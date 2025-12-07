"""Reaction-Diffusion base class for pattern drawers."""

from abc import abstractmethod
import numpy as np
from scipy import ndimage
from aurora_web.drawers.base import Drawer, DrawerContext

# Laplacian kernel for convolution (5-point stencil)
LAPLACIAN_KERNEL = np.array([[0, 1, 0],
                              [1, -4, 1],
                              [0, 1, 0]], dtype=np.float32)


class ReactionDiffusionDrawer(Drawer):
    """Base class for reaction-diffusion pattern drawers.

    Implements common functionality for two-component (U, V) reaction-diffusion
    systems with diffusion via Laplacian operator.
    """

    def __init__(self, name: str, width: int, height: int, palette_size: int = 4096):
        super().__init__(name, width, height, palette_size)

        # Double-buffered U and V concentration arrays
        self.u = [None, None]
        self.v = [None, None]
        self.q = 0  # Current buffer index

        # Simulation parameters
        self.color_index = 0
        self.speed = 1
        self.scale = 1.0
        self.last_max_v = 0.0

    def _laplacian(self, arr: np.ndarray) -> np.ndarray:
        """Compute discrete Laplacian with periodic boundary conditions.

        Uses scipy.ndimage.convolve for optimized performance.
        """
        return ndimage.convolve(arr, LAPLACIAN_KERNEL, mode='wrap')

    def reset_to_values(self, bg_u: float, bg_v: float, fg_u: float, fg_v: float) -> None:
        """Reset with background values and random foreground islands.

        Args:
            bg_u: Background U value
            bg_v: Background V value
            fg_u: Foreground (island) U value
            fg_v: Foreground (island) V value
        """
        for q in range(2):
            self.u[q] = np.full((self.height, self.width), bg_u, dtype=np.float32)
            self.v[q] = np.full((self.height, self.width), bg_v, dtype=np.float32)

        # Add random islands
        num_islands = 5
        island_size = min(20, min(self.width, self.height) // 4)

        for _ in range(num_islands):
            cx = np.random.randint(island_size, self.width - island_size)
            cy = np.random.randint(island_size, self.height - island_size)
            half = island_size // 2

            self.u[0][cy-half:cy+half, cx-half:cx+half] = fg_u
            self.v[0][cy-half:cy+half, cx-half:cx+half] = fg_v
            self.u[1][cy-half:cy+half, cx-half:cx+half] = fg_u
            self.v[1][cy-half:cy+half, cx-half:cx+half] = fg_v

        self.q = 0
        self.color_index = 0

    def reset_random(self, low: float, high: float) -> None:
        """Reset with random values in range [low, high].

        Args:
            low: Minimum random value
            high: Maximum random value
        """
        for q in range(2):
            self.u[q] = np.random.uniform(low, high, (self.height, self.width)).astype(np.float32)
            self.v[q] = np.random.uniform(low, high, (self.height, self.width)).astype(np.float32)

        self.q = 0
        self.color_index = 0

    @abstractmethod
    def _step_uv(self) -> None:
        """Perform one reaction-diffusion step. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def _set_params(self) -> None:
        """Set simulation parameters. Must be implemented by subclasses."""
        pass

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        """Draw one frame of the reaction-diffusion simulation.

        Returns:
            Array of palette indices, shape (height, width)
        """
        # Run simulation steps based on speed
        for _ in range(self.speed):
            self._step_uv()

        # Get V values and normalize to palette indices
        v = self.v[self.q]

        # Track max V for normalization
        max_v = np.max(v)
        if max_v > 0:
            self.last_max_v = max(self.last_max_v * 0.99, max_v)

        # Normalize V to [0, 1]
        if self.last_max_v > 0:
            v_norm = np.clip(v / self.last_max_v, 0, 1)
        else:
            v_norm = v

        # Convert to palette indices
        indices = (v_norm * (self.palette_size - 1)).astype(np.int32)

        # Apply color cycling
        indices = (indices + self.color_index) % self.palette_size
        self.color_index = (self.color_index + self.settings.get("colorSpeed", 0)) % self.palette_size

        return indices
