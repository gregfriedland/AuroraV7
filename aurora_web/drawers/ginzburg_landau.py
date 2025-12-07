"""Ginzburg-Landau drawer - complex reaction-diffusion pattern generator."""

import numpy as np
from aurora_web.drawers.reaction_diffusion import ReactionDiffusionDrawer
from aurora_web.drawers.base import DrawerContext


# Parameter sets for different visual effects
GINZBURG_LANDAU_PARAM_SETS = [
    {"alpha": 0.0625, "beta": 1.0, "gamma": 0.0625, "delta": 1.0, "scale_range": (1.0, 1.0)},
    {"alpha": 0.0625, "beta": 1.0, "gamma": 0.0625, "delta": 1.0, "scale_range": (0.5, 20.0)},
]


class GinzburgLandauDrawer(ReactionDiffusionDrawer):
    """Ginzburg-Landau reaction-diffusion pattern generator.

    Creates spiral waves and turbulent patterns using the complex
    Ginzburg-Landau equation, which models pattern formation in
    oscillatory media.

    The equations (in real-valued form with u=Re, v=Im):
        du/dt = Du*lap_u + alpha*u - gamma*v + (-beta*u + delta*v)*(u^2+v^2)
        dv/dt = Dv*lap_v + alpha*v + gamma*u + (-beta*v - delta*u)*(u^2+v^2)

    Where:
        - alpha controls linear growth
        - beta controls nonlinear saturation
        - gamma controls rotation (imaginary linear term)
        - delta controls nonlinear rotation
    """

    def __init__(self, width: int, height: int, palette_size: int = 4096):
        super().__init__("GinzburgLandau", width, height, palette_size)

        # Settings
        self.settings = {
            "speed": 10,
            "colorSpeed": 0,
            "params": 1,
        }
        self.settings_ranges = {
            "speed": (5, 10),
            "colorSpeed": (0, 10),
            "params": (0, len(GINZBURG_LANDAU_PARAM_SETS) - 1),
        }

        # Ginzburg-Landau specific parameters
        self.alpha = 0.0625
        self.beta = 1.0
        self.gamma = 0.0625
        self.delta = 1.0
        self.dt = 0.2
        self.du = 0.2
        self.dv = 0.2

        self.reset()

    def reset(self) -> None:
        """Reset with small random perturbations."""
        self.reset_random(low=-0.25, high=0.25)
        self._set_params()

    def _set_params(self) -> None:
        """Set simulation parameters based on current param set."""
        params = GINZBURG_LANDAU_PARAM_SETS[self.settings["params"]]
        self.alpha = params["alpha"]
        self.beta = params["beta"]
        self.gamma = params["gamma"]
        self.delta = params["delta"]

        # Random scale for variety
        scale_range = params["scale_range"]
        self.scale = np.exp(np.random.uniform(np.log(scale_range[0]), np.log(scale_range[1])))

        # Adjust diffusion and time step based on scale
        self.du = 0.2 * self.scale
        self.dv = 0.2 * self.scale
        self.dt = 0.2 / self.scale

        # Speed limited to maintain framerate
        max_speed = 7
        self.speed = min(max_speed, int(self.settings["speed"] * self.scale))
        self.speed = max(1, self.speed)

    def _step_uv(self) -> None:
        """Perform one Ginzburg-Landau reaction-diffusion step."""
        u = self.u[self.q]
        v = self.v[self.q]

        # Compute Laplacians
        lap_u = self._laplacian(u)
        lap_v = self._laplacian(v)

        # u^2 + v^2
        uv_sq = u * u + v * v

        # Ginzburg-Landau equations
        # du/dt = Du*lap_u + alpha*u - gamma*v + (-beta*u + delta*v)*(u^2+v^2)
        du_dt = (
            self.du * lap_u +
            self.alpha * u -
            self.gamma * v +
            (-self.beta * u + self.delta * v) * uv_sq
        )

        # dv/dt = Dv*lap_v + alpha*v + gamma*u + (-beta*v - delta*u)*(u^2+v^2)
        dv_dt = (
            self.dv * lap_v +
            self.alpha * v +
            self.gamma * u +
            (-self.beta * v - self.delta * u) * uv_sq
        )

        # Euler integration
        u_new = u + self.dt * du_dt
        v_new = v + self.dt * dv_dt

        # Store in next buffer (no clamping for GL - values can go negative)
        next_q = 1 - self.q
        self.u[next_q] = u_new
        self.v[next_q] = v_new
        self.q = next_q

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        """Draw one frame of the Ginzburg-Landau simulation.

        For GL, we visualize the phase angle of the complex field (u + iv).

        Returns:
            Array of palette indices, shape (height, width)
        """
        # Run simulation steps based on speed
        for _ in range(self.speed):
            self._step_uv()

        # Get U and V values
        u = self.u[self.q]
        v = self.v[self.q]

        # Compute phase angle (atan2 gives [-pi, pi])
        phase = np.arctan2(v, u)

        # Normalize phase to [0, 1]
        phase_norm = (phase + np.pi) / (2 * np.pi)

        # Convert to palette indices
        indices = (phase_norm * (self.palette_size - 1)).astype(np.int32)

        # Apply color cycling
        indices = (indices + self.color_index) % self.palette_size
        self.color_index = (self.color_index + self.settings.get("colorSpeed", 0)) % self.palette_size

        return indices
