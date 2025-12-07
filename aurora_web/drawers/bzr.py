"""Bzr drawer - Belousov-Zhabotinsky reaction simulation."""

import numpy as np
from aurora_web.drawers.base import Drawer, DrawerContext


# Parameter sets for different visual effects
BZR_PARAM_SETS = [
    {"ka": 0.5, "kb": 0.5, "kc": 0.6},
    {"ka": 1.1, "kb": 1.1, "kc": 0.9},
    {"ka": 0.9, "kb": 1.0, "kc": 1.1},
    {"ka": 0.9, "kb": 0.9, "kc": 1.1},
    {"ka": 1.0, "kb": 1.0, "kc": 1.1},
    {"ka": 1.0, "kb": 1.0, "kc": 1.0},
    {"ka": 0.5, "kb": 0.5, "kc": 0.5},
    {"ka": 0.75, "kb": 0.75, "kc": 0.75},
]


class BzrDrawer(Drawer):
    """Belousov-Zhabotinsky reaction simulation.

    Creates mesmerizing spiral patterns through a chemical reaction simulation.
    Uses three coupled chemical concentrations (a, b, c) that interact via
    reaction-diffusion dynamics.
    """

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("Bzr", width, height, palette_size)

        # Settings
        self.settings = {
            "speed": 50,
            "colorSpeed": 0,
            "zoom": 70,
            "params": 0,
        }
        self.settings_ranges = {
            "speed": (10, 100),
            "colorSpeed": (0, 50),
            "zoom": (30, 100),
            "params": (0, len(BZR_PARAM_SETS) - 1),
        }

        # Simulation runs at higher resolution for quality
        self.bzr_width = max(192, width)
        self.bzr_height = max(96, height)

        # Double-buffered state arrays
        self.a = [None, None]
        self.b = [None, None]
        self.c = [None, None]
        self.q = 0  # Current buffer index

        # Animation state
        self.color_index = 0
        self.state = 0
        self.num_states = 1

        # Reaction parameters
        self.ka = 0.5
        self.kb = 0.5
        self.kc = 0.6

        self.reset()

    def reset(self) -> None:
        """Reset simulation with random initial conditions."""
        # Initialize concentration arrays with random values
        for q in range(2):
            self.a[q] = np.random.rand(self.bzr_height, self.bzr_width).astype(np.float32)
            self.b[q] = np.random.rand(self.bzr_height, self.bzr_width).astype(np.float32)
            self.c[q] = np.random.rand(self.bzr_height, self.bzr_width).astype(np.float32)

        self.q = 0
        self.state = 0
        self.color_index = 0

        # Set reaction parameters based on param set
        params = BZR_PARAM_SETS[self.settings["params"]]
        self.ka = params["ka"]
        self.kb = params["kb"]
        self.kc = params["kc"]

    def _neighbor_avg(self, arr: np.ndarray) -> np.ndarray:
        """Compute 3x3 neighborhood average using convolution."""
        # Efficient neighbor averaging with wrap-around boundary
        result = np.zeros_like(arr)
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                result += np.roll(np.roll(arr, dy, axis=0), dx, axis=1)
        return result / 9.0

    def _step_simulation(self) -> None:
        """Perform one simulation step."""
        # Get current buffer
        a_curr = self.a[self.q]
        b_curr = self.b[self.q]
        c_curr = self.c[self.q]

        # Compute neighborhood averages
        a_avg = self._neighbor_avg(a_curr)
        b_avg = self._neighbor_avg(b_curr)
        c_avg = self._neighbor_avg(c_curr)

        # BZ reaction equations
        # a' = avg_a + a * (ka * b - kc * c)
        # b' = avg_b + b * (kb * c - ka * a)
        # c' = avg_c + c * (kc * a - kb * b)
        next_idx = 1 - self.q

        self.a[next_idx] = np.clip(
            a_avg + a_curr * (self.ka * b_curr - self.kc * c_curr),
            0.0, 1.0
        )
        self.b[next_idx] = np.clip(
            b_avg + b_curr * (self.kb * c_curr - self.ka * a_curr),
            0.0, 1.0
        )
        self.c[next_idx] = np.clip(
            c_avg + c_curr * (self.kc * a_curr - self.kb * b_curr),
            0.0, 1.0
        )

        self.q = next_idx

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        """Draw one frame of the BZ reaction.

        Returns:
            Array of palette indices, shape (height, width)
        """
        speed = self.settings["speed"] / 100.0

        # Calculate number of interpolation states based on speed
        # Higher speed = fewer states = faster animation
        self.num_states = max(1, int(100 - speed * 99))

        if self.state >= self.num_states:
            self.state = 0

        # Only step simulation at state 0
        if self.state == 0:
            self._step_simulation()

        # Sample from simulation at display resolution
        # Use zoom to control sampling (currently fixed at 1:1)
        x_scale = self.bzr_width / self.width
        y_scale = self.bzr_height / self.height

        # Create index arrays for sampling
        x_indices = (np.arange(self.width) * x_scale).astype(np.int32) % self.bzr_width
        y_indices = (np.arange(self.height) * y_scale).astype(np.int32) % self.bzr_height

        # Sample with interpolation between frames
        a_curr = self.a[self.q]
        a_prev = self.a[1 - self.q]

        # Interpolate between previous and current state
        t = self.state / max(1, self.num_states)
        a_interp = a_prev * (1 - t) + a_curr * t

        # Sample at display resolution
        indices = np.zeros((self.height, self.width), dtype=np.int32)
        for y in range(self.height):
            for x in range(self.width):
                val = a_interp[y_indices[y], x_indices[x]]
                indices[y, x] = int(val * (self.palette_size - 1))

        self.state += 1

        # Apply color cycling
        indices = (indices + self.color_index) % self.palette_size
        self.color_index = (self.color_index + self.settings["colorSpeed"]) % self.palette_size

        return indices
