"""Drawer manager for mode switching and drawer orchestration."""

import random
import time
import numpy as np
from scipy.stats import entropy

from aurora_web.core.palette import Palette
from aurora_web.drawers.base import Drawer, DrawerContext


class DrawerManager:
    """Manages pattern drawers and mode switching.

    Handles switching between paint mode (browser-sourced frames) and
    pattern mode (server-generated frames from drawers).
    """

    # Auto-rotation settings
    AUTO_ROTATE_INTERVAL = 60.0  # seconds between auto-rotations
    USER_INTERACTION_COOLDOWN = 15 * 60.0  # 15 minutes cooldown after user interaction
    LOW_ENTROPY_THRESHOLD = 1.0  # bits - below this is considered "stuck"
    LOW_ENTROPY_DURATION = 1.0  # seconds of low entropy before triggering rotation

    def __init__(self, width: int, height: int, palette_size: int = 4096, beat_feed=None, audio_feed=None):
        """Initialize drawer manager.

        Args:
            width: Matrix width
            height: Matrix height
            palette_size: Size of color palette
        """
        self.width = width
        self.height = height
        self.palette_size = palette_size
        self.beat_feed = beat_feed
        self.audio_feed = audio_feed

        # Drawer registry
        self.drawers: dict[str, Drawer] = {}
        self.active_drawer: Drawer | None = None

        # Mode: "paint" or "pattern"
        self.mode = "paint"

        # Color palette for pattern mode
        self.palette = Palette(size=palette_size)
        self.current_palette_index = 0

        # Timing
        self.frame_num = 0
        self.start_time = time.time()
        self.last_time = self.start_time

        # Auto-rotation state
        self.last_rotation_time = time.time()
        self.last_user_interaction = 0.0  # No interaction yet

        # Entropy tracking for stuck pattern detection
        self.low_entropy_start = None  # When low entropy was first detected
        self.last_entropy = 0.0

        # Callback on drawer change: fn(old_name, new_name)
        self._on_drawer_change: callable = None

        # Default black frame
        self.black_frame = np.zeros((height, width, 3), dtype=np.uint8)

    def register_drawer(self, drawer: Drawer) -> None:
        """Register a drawer.

        Args:
            drawer: Drawer instance to register
        """
        self.drawers[drawer.name] = drawer

    def get_drawer_list(self) -> list[dict]:
        """Get list of available drawers with their info.

        Returns:
            List of drawer info dicts
        """
        return [
            {
                "name": name,
                "settings": drawer.get_settings_info()
            }
            for name, drawer in self.drawers.items()
        ]

    def set_mode(self, mode: str) -> bool:
        """Set current mode.

        Args:
            mode: "paint" or "pattern"

        Returns:
            True if mode was changed
        """
        if mode in ("paint", "pattern"):
            self.mode = mode
            return True
        return False

    def set_active_drawer(self, name: str) -> bool:
        """Set the active drawer by name.

        Args:
            name: Drawer name

        Returns:
            True if drawer was found and set
        """
        if name in self.drawers:
            old_name = self.active_drawer.name if self.active_drawer else None
            self.active_drawer = self.drawers[name]
            self.active_drawer.reset()
            if self._on_drawer_change and old_name != name:
                self._on_drawer_change(old_name, name)
            return True
        return False

    def update_drawer_settings(self, settings: dict[str, int]) -> bool:
        """Update settings on active drawer.

        Args:
            settings: Dict of setting name to value

        Returns:
            True if settings were updated
        """
        if self.active_drawer:
            self.active_drawer.update_settings(settings)
            return True
        return False

    def set_palette_colors(self, base_colors: list[tuple]) -> None:
        """Update palette with new base colors.

        Args:
            base_colors: List of (R, G, B) tuples
        """
        self.palette.set_base_colors(base_colors)

    def get_frame(self, browser_frame: np.ndarray | None = None) -> np.ndarray:
        """Get current frame based on mode.

        Args:
            browser_frame: Frame from browser (used in paint mode)

        Returns:
            RGB frame array, shape (height, width, 3)
        """
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        self.frame_num += 1

        if self.mode == "paint":
            # Use browser frame or black
            return browser_frame if browser_frame is not None else self.black_frame

        elif self.mode == "pattern" and self.active_drawer:
            # Generate frame from drawer
            ctx = DrawerContext(
                width=self.width,
                height=self.height,
                frame_num=self.frame_num,
                time=current_time - self.start_time,
                delta_time=delta_time,
                palette_size=self.palette_size,
                beat_onsets=self.beat_feed.get_onsets() if self.beat_feed else (),
                audio=self.audio_feed.get_input() if self.audio_feed else None,
            )

            # Get frame from drawer
            result = self.active_drawer.draw(ctx)

            # Drawer returns RGB directly (e.g. LiveCodeDrawer)
            if getattr(self.active_drawer, "returns_rgb", False):
                return result

            # Otherwise result is palette indices — convert to RGB
            self._update_entropy(result, current_time)
            rgb = self.palette.indices_to_rgb(result)

            # Restart with random settings if stuck (all one color for 2s).
            # Audio-driven drawers are exempt: silence legitimately renders black.
            if self.is_entropy_stuck() and not getattr(self.active_drawer, "reacts_to_audio", False):
                print(f"[DrawerManager] Pattern stuck ({self.last_entropy:.2f} bits), randomizing settings")
                self.low_entropy_start = None
                self.active_drawer.randomize_settings()

            return rgb

        else:
            return self.black_frame

    def get_status(self) -> dict:
        """Get current status for UI.

        Returns:
            Status dict
        """
        return {
            "mode": self.mode,
            "active_drawer": self.active_drawer.name if self.active_drawer else None,
            "drawers": list(self.drawers.keys()),
            "auto_rotate_active": self.is_auto_rotate_active(),
            "palette_index": self.current_palette_index,
            "entropy": round(self.last_entropy, 2),
        }

    def user_interacted(self) -> None:
        """Mark that user has interacted, disabling auto-rotation temporarily."""
        self.last_user_interaction = time.time()

    def is_auto_rotate_active(self) -> bool:
        """Check if auto-rotation is currently active.

        Returns:
            True if auto-rotation is active (no recent user interaction)
        """
        time_since_interaction = time.time() - self.last_user_interaction
        return time_since_interaction >= self.USER_INTERACTION_COOLDOWN

    def randomize_all(self) -> dict:
        """Randomize drawer, settings, and palette.

        Returns:
            Dict with new drawer name, palette index, and settings
        """
        # Pick a random drawer (excluding "Off")
        available_drawers = [name for name in self.drawers.keys() if name != "Off"]
        if not available_drawers:
            return {}

        drawer_name = random.choice(available_drawers)
        self.set_active_drawer(drawer_name)

        # Randomize the drawer's settings
        if self.active_drawer:
            self.active_drawer.randomize_settings()

        # Pick a random curated palette
        self.current_palette_index = random.randint(0, Palette.curated_count() - 1)
        self.palette.set_curated(self.current_palette_index)

        # Reset rotation timer
        self.last_rotation_time = time.time()

        return {
            "drawer": drawer_name,
            "palette_index": self.current_palette_index,
            "settings": self.active_drawer.get_settings_info() if self.active_drawer else {},
        }

    def _update_entropy(self, indices: np.ndarray, current_time: float) -> None:
        """Update entropy tracking for stuck pattern detection.

        Args:
            indices: Array of palette indices
            current_time: Current timestamp
        """
        # Calculate entropy using histogram of index values
        # Use 256 bins for efficiency (quantize indices)
        flat = indices.flatten()
        hist, _ = np.histogram(flat, bins=256, range=(0, self.palette_size))
        hist = hist[hist > 0]  # Remove zero bins
        if len(hist) > 0:
            probs = hist / hist.sum()
            self.last_entropy = entropy(probs, base=2)
        else:
            self.last_entropy = 0.0

        # Track low entropy duration
        if self.last_entropy < self.LOW_ENTROPY_THRESHOLD:
            if self.low_entropy_start is None:
                self.low_entropy_start = current_time
        else:
            self.low_entropy_start = None

    def is_entropy_stuck(self) -> bool:
        """Check if pattern has been stuck (low entropy) for too long.

        Returns:
            True if entropy has been low for longer than LOW_ENTROPY_DURATION
        """
        if self.low_entropy_start is None:
            return False
        return (time.time() - self.low_entropy_start) >= self.LOW_ENTROPY_DURATION

    def check_auto_rotate(self) -> dict | None:
        """Check if it's time to auto-rotate and do so if needed.

        Returns:
            Dict with new state if rotated, None otherwise
        """
        if not self.is_auto_rotate_active():
            return None

        if self.mode != "pattern":
            return None

        # Never rotate pattern/palette away from audio-reactive drawers
        if self.active_drawer and getattr(self.active_drawer, "reacts_to_audio", False):
            return None

        # Check for time-based rotation
        time_since_rotation = time.time() - self.last_rotation_time
        if time_since_rotation >= self.AUTO_ROTATE_INTERVAL:
            print(f"[DrawerManager] Auto-rotating after {self.AUTO_ROTATE_INTERVAL}s")
            return self.randomize_all()

        return None
