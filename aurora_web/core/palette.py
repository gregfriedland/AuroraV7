"""Color palette for converting palette indices to RGB."""

import numpy as np

from aurora_web.core.curated_palettes import CURATED_PALETTES, get_palette_count


class Palette:
    """Color palette with smooth gradient interpolation.

    Creates a palette of colors by interpolating between base colors.
    """

    def __init__(self, size: int = 4096, base_colors: list[tuple[int, int, int]] | None = None):
        """Initialize palette.

        Args:
            size: Number of colors in the palette
            base_colors: List of (R, G, B) tuples to interpolate between.
                        If None, uses a default rainbow gradient.
        """
        self.size = size

        if base_colors is None:
            # Default rainbow gradient
            base_colors = [
                (255, 0, 0),     # Red
                (255, 127, 0),   # Orange
                (255, 255, 0),   # Yellow
                (0, 255, 0),     # Green
                (0, 255, 255),   # Cyan
                (0, 0, 255),     # Blue
                (127, 0, 255),   # Purple
                (255, 0, 255),   # Magenta
                (255, 0, 0),     # Back to red for seamless wrap
            ]

        self._build_lut(base_colors)

    def _build_lut(self, base_colors: list[tuple[int, int, int]]) -> None:
        """Build the color lookup table by interpolating base colors."""
        self.lut = np.zeros((self.size, 3), dtype=np.uint8)

        num_segments = len(base_colors) - 1
        colors_per_segment = self.size // num_segments

        idx = 0
        for i in range(num_segments):
            c1 = np.array(base_colors[i], dtype=np.float32)
            c2 = np.array(base_colors[i + 1], dtype=np.float32)

            # Handle last segment - may need extra colors
            segment_len = colors_per_segment
            if i == num_segments - 1:
                segment_len = self.size - idx

            for j in range(segment_len):
                t = j / max(segment_len - 1, 1)
                color = c1 + (c2 - c1) * t
                self.lut[idx] = color.astype(np.uint8)
                idx += 1

    def get_color(self, index: int) -> tuple[int, int, int]:
        """Get color at palette index.

        Args:
            index: Palette index (will be wrapped to size)

        Returns:
            Tuple of (R, G, B)
        """
        idx = index % self.size
        return tuple(self.lut[idx])

    def indices_to_rgb(self, indices: np.ndarray) -> np.ndarray:
        """Convert array of palette indices to RGB frame.

        Args:
            indices: 2D array of palette indices, shape (height, width)

        Returns:
            RGB array, shape (height, width, 3), dtype uint8
        """
        # Wrap indices to palette size
        wrapped = indices % self.size
        # Use fancy indexing to look up colors
        return self.lut[wrapped]

    def set_base_colors(self, base_colors: list[tuple[int, int, int]]) -> None:
        """Update palette with new base colors.

        Args:
            base_colors: List of (R, G, B) tuples to interpolate between
        """
        self._build_lut(base_colors)

    @classmethod
    def from_curated(cls, index: int, size: int = 4096) -> "Palette":
        """Create a palette from the curated collection.

        Args:
            index: Curated palette index (0-199, wraps around)
            size: Number of colors in the palette

        Returns:
            Palette initialized with curated colors
        """
        curated_colors = CURATED_PALETTES[index % len(CURATED_PALETTES)]
        return cls(size=size, base_colors=curated_colors)

    def set_curated(self, index: int) -> None:
        """Set palette to a curated palette by index.

        Args:
            index: Curated palette index (0-199, wraps around)
        """
        curated_colors = CURATED_PALETTES[index % len(CURATED_PALETTES)]
        self._build_lut(curated_colors)

    @staticmethod
    def curated_count() -> int:
        """Return the number of available curated palettes."""
        return get_palette_count()


def create_gradient_palette(
    color1: tuple[int, int, int],
    color2: tuple[int, int, int],
    size: int = 256
) -> Palette:
    """Create a simple two-color gradient palette.

    Args:
        color1: Start color (R, G, B)
        color2: End color (R, G, B)
        size: Number of colors

    Returns:
        Palette with gradient from color1 to color2
    """
    return Palette(size=size, base_colors=[color1, color2])
