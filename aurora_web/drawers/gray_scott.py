"""Gray-Scott drawer - reaction-diffusion pattern generator."""

import numpy as np
from aurora_web.drawers.reaction_diffusion import ReactionDiffusionDrawer
from aurora_web.drawers.base import DrawerContext


# Parameter sets from http://mrob.com/pub/comp/xmorphia
GRAY_SCOTT_PARAM_SETS = [
    {"F": 0.022, "k": 0.049, "scale_range": (0.5, 20)},   # Mitosis
    {"F": 0.026, "k": 0.051, "scale_range": (0.5, 20)},   # Coral growth
    {"F": 0.026, "k": 0.052, "scale_range": (0.5, 20)},   # Moving spots
    {"F": 0.022, "k": 0.048, "scale_range": (0.5, 20)},   # Worms
    {"F": 0.018, "k": 0.045, "scale_range": (0.5, 20)},   # Solitons
    {"F": 0.010, "k": 0.033, "scale_range": (0.5, 10)},   # Pulsating solitons
    {"F": 0.014, "k": 0.041, "scale_range": (0.5, 5)},    # Mazes (may end quickly)
    {"F": 0.006, "k": 0.045, "scale_range": (1.0, 5)},    # Holes (may end quickly)
    {"F": 0.010, "k": 0.047, "scale_range": (1.0, 5)},    # Chaos (may end quickly)
]


class GrayScottDrawer(ReactionDiffusionDrawer):
    """Gray-Scott reaction-diffusion pattern generator.

    Creates organic growth patterns, coral-like structures, and cellular
    automata-like behaviors through a two-chemical reaction-diffusion system.

    The Gray-Scott equations:
        du/dt = Du * laplacian(u) - u*v^2 + F*(1-u)
        dv/dt = Dv * laplacian(v) + u*v^2 - (F+k)*v

    Where:
        - F is the feed rate (replenishes u)
        - k is the kill rate (removes v)
        - Du, Dv are diffusion rates
    """

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("GrayScott", width, height, palette_size)

        # Settings - limit params on small panels
        max_params = 5 if (width < 64 or height < 64) else len(GRAY_SCOTT_PARAM_SETS) - 1

        self.settings = {
            "speed": 10,
            "colorSpeed": 10,
            "params": 1,
        }
        self.settings_ranges = {
            "speed": (5, 10),
            "colorSpeed": (5, 15),
            "params": (0, max_params),
        }

        # Gray-Scott specific parameters
        self.F = 0.026
        self.k = 0.051
        self.dt = 1.0
        self.du = 0.08
        self.dv = 0.04

        self.reset()

    def reset(self) -> None:
        """Reset with initial islands of V in a field of U."""
        self.reset_to_values(bg_u=1.0, bg_v=0.0, fg_u=0.5, fg_v=0.25)
        self._set_params()

    def _set_params(self) -> None:
        """Set simulation parameters based on current param set."""
        params = GRAY_SCOTT_PARAM_SETS[self.settings["params"]]
        self.F = params["F"]
        self.k = params["k"]

        # Random scale for variety
        scale_range = params["scale_range"]
        self.scale = np.exp(np.random.uniform(np.log(scale_range[0]), np.log(scale_range[1])))

        # Adjust diffusion and time step based on scale
        self.du = 0.08 * self.scale
        self.dv = 0.04 * self.scale
        self.dt = 1.0 / self.scale

        # Speed limited to maintain framerate
        max_speed = 40
        self.speed = min(max_speed, int(self.settings["speed"] * self.scale))
        self.speed = max(1, self.speed)

    def _step_uv(self) -> None:
        """Perform one Gray-Scott reaction-diffusion step."""
        u = self.u[self.q]
        v = self.v[self.q]

        # Compute Laplacians
        lap_u = self._laplacian(u)
        lap_v = self._laplacian(v)

        # Gray-Scott equations
        uvv = u * v * v

        # du/dt = Du * lap_u - uvv + F*(1-u)
        u_new = u + self.dt * (self.du * lap_u - uvv + self.F * (1.0 - u))

        # dv/dt = Dv * lap_v + uvv - (F+k)*v
        v_new = v + self.dt * (self.dv * lap_v + uvv - (self.F + self.k) * v)

        # Store in next buffer
        next_q = 1 - self.q
        self.u[next_q] = np.clip(u_new, 0, 1)
        self.v[next_q] = np.clip(v_new, 0, 1)
        self.q = next_q
