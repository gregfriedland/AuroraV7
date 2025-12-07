"""Custom drawer that loads and executes YAML drawer definitions."""

import numpy as np
import yaml
import math
from pathlib import Path
from typing import Any, Callable

from aurora_web.drawers.base import Drawer, DrawerContext


class CustomDrawer(Drawer):
    """Drawer that runs user-defined Python code from a YAML definition.

    YAML format:
        name: "My Pattern"
        author: "username"
        description: "Pattern description"

        uses:
            audio: false
            video: false
            canvas: true

        settings:
            speed:
                type: float
                default: 1.0
                min: 0.1
                max: 5.0
                description: "Animation speed"

        code: |
            def draw(width, height, ctx, settings, palette_size):
                indices = np.zeros((height, width), dtype=np.int32)
                t = ctx.time * settings['speed']
                ...
                return indices
    """

    def __init__(
        self,
        width: int,
        height: int,
        palette_size: int = 4096,
        yaml_path: Path | None = None,
        yaml_content: str | None = None,
    ):
        """Initialize custom drawer.

        Args:
            width: Matrix width
            height: Matrix height
            palette_size: Number of palette colors
            yaml_path: Path to YAML file (optional)
            yaml_content: YAML content as string (optional)
        """
        # Load YAML definition
        if yaml_path:
            self.yaml_path = Path(yaml_path)
            with open(yaml_path, 'r') as f:
                self.definition = yaml.safe_load(f)
        elif yaml_content:
            self.yaml_path = None
            self.definition = yaml.safe_load(yaml_content)
        else:
            raise ValueError("Either yaml_path or yaml_content must be provided")

        name = self.definition.get('name', 'Custom')
        super().__init__(name, width, height, palette_size)

        self.author = self.definition.get('author', 'unknown')
        self.description = self.definition.get('description', '')
        self.uses_audio = self.definition.get('uses', {}).get('audio', False)
        self.uses_video = self.definition.get('uses', {}).get('video', False)
        self.uses_canvas = self.definition.get('uses', {}).get('canvas', False)

        # Parse settings
        self._parse_settings()

        # Compile the draw function
        self._draw_func: Callable | None = None
        self._compile_code()

        # State for persistent variables
        self._state: dict[str, Any] = {}

    def _parse_settings(self) -> None:
        """Parse settings from YAML definition."""
        settings_def = self.definition.get('settings', {})

        for key, spec in settings_def.items():
            if isinstance(spec, dict):
                default = spec.get('default', 0)
                min_val = spec.get('min', 0)
                max_val = spec.get('max', 100)

                # Convert to int for compatibility with base class
                if spec.get('type') in ('int', 'float'):
                    self.settings[key] = default
                    self.settings_ranges[key] = (min_val, max_val)
                elif spec.get('type') == 'bool':
                    self.settings[key] = 1 if default else 0
                    self.settings_ranges[key] = (0, 1)
            else:
                # Simple value
                self.settings[key] = spec
                self.settings_ranges[key] = (0, 100)

    def _compile_code(self) -> None:
        """Compile the Python code from YAML definition."""
        code_str = self.definition.get('code', '')
        if not code_str:
            raise ValueError("No 'code' section found in YAML definition")

        # Create a restricted namespace for execution
        namespace = {
            'np': np,
            'numpy': np,
            'math': math,
            '__builtins__': {
                'range': range,
                'len': len,
                'int': int,
                'float': float,
                'abs': abs,
                'min': min,
                'max': max,
                'sum': sum,
                'enumerate': enumerate,
                'zip': zip,
                'map': map,
                'filter': filter,
                'list': list,
                'tuple': tuple,
                'dict': dict,
                'set': set,
                'bool': bool,
                'str': str,
                'getattr': getattr,
                'setattr': setattr,
                'hasattr': hasattr,
                'isinstance': isinstance,
                'print': print,  # For debugging
            }
        }

        try:
            # Execute the code to define the draw function
            exec(code_str, namespace)

            if 'draw' not in namespace:
                raise ValueError("Code must define a 'draw' function")

            self._draw_func = namespace['draw']
            self._namespace = namespace

        except Exception as e:
            raise ValueError(f"Failed to compile custom drawer code: {e}")

    def reset(self) -> None:
        """Reset drawer state."""
        self._state = {}

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        """Execute the custom draw function.

        Args:
            ctx: DrawerContext with frame timing

        Returns:
            2D array of palette indices
        """
        if self._draw_func is None:
            return np.zeros((self.height, self.width), dtype=np.int32)

        try:
            # Call the user's draw function
            result = self._draw_func(
                self.width,
                self.height,
                ctx,
                self.settings,
                self.palette_size,
            )

            # Ensure result is the right type and shape
            if not isinstance(result, np.ndarray):
                result = np.array(result)

            result = result.astype(np.int32)

            if result.shape != (self.height, self.width):
                # Try to reshape or pad/crop
                if result.size == self.height * self.width:
                    result = result.reshape((self.height, self.width))
                else:
                    # Create zeros and copy what fits
                    output = np.zeros((self.height, self.width), dtype=np.int32)
                    h = min(result.shape[0], self.height)
                    w = min(result.shape[1], self.width)
                    output[:h, :w] = result[:h, :w]
                    result = output

            # Ensure indices are within palette range
            return np.clip(result, 0, self.palette_size - 1)

        except Exception as e:
            print(f"[CustomDrawer] Error in draw(): {e}")
            return np.zeros((self.height, self.width), dtype=np.int32)

    def to_yaml(self) -> str:
        """Export drawer definition as YAML string.

        Returns:
            YAML string representation
        """
        return yaml.dump(self.definition, default_flow_style=False)

    @classmethod
    def from_yaml_string(
        cls,
        yaml_content: str,
        width: int,
        height: int,
        palette_size: int = 4096,
    ) -> 'CustomDrawer':
        """Create CustomDrawer from YAML string.

        Args:
            yaml_content: YAML definition as string
            width: Matrix width
            height: Matrix height
            palette_size: Palette size

        Returns:
            CustomDrawer instance
        """
        return cls(
            width=width,
            height=height,
            palette_size=palette_size,
            yaml_content=yaml_content,
        )


class CustomDrawerLoader:
    """Loads and manages custom drawers from a directory."""

    def __init__(
        self,
        custom_drawers_path: Path,
        width: int,
        height: int,
        palette_size: int = 4096,
    ):
        """Initialize loader.

        Args:
            custom_drawers_path: Path to custom drawers directory
            width: Matrix width
            height: Matrix height
            palette_size: Palette size
        """
        self.base_path = Path(custom_drawers_path)
        self.width = width
        self.height = height
        self.palette_size = palette_size

        # Ensure directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    def list_drawers(self, username: str | None = None) -> list[dict[str, str]]:
        """List available custom drawers.

        Args:
            username: Optional username to filter by

        Returns:
            List of drawer info dicts with 'name', 'author', 'path', 'description'
        """
        drawers = []

        search_path = self.base_path / username if username else self.base_path

        if not search_path.exists():
            return drawers

        # Search for YAML files
        pattern = "**/*.yaml" if not username else "*.yaml"
        for yaml_file in search_path.glob(pattern):
            try:
                with open(yaml_file, 'r') as f:
                    definition = yaml.safe_load(f)

                drawers.append({
                    'name': definition.get('name', yaml_file.stem),
                    'author': definition.get('author', 'unknown'),
                    'description': definition.get('description', ''),
                    'path': str(yaml_file.relative_to(self.base_path)),
                    'created': definition.get('created', ''),
                })
            except Exception as e:
                print(f"[CustomDrawerLoader] Error loading {yaml_file}: {e}")

        return drawers

    def load_drawer(self, relative_path: str) -> CustomDrawer:
        """Load a custom drawer by relative path.

        Args:
            relative_path: Path relative to custom_drawers directory

        Returns:
            CustomDrawer instance
        """
        yaml_path = self.base_path / relative_path
        return CustomDrawer(
            width=self.width,
            height=self.height,
            palette_size=self.palette_size,
            yaml_path=yaml_path,
        )

    def save_drawer(
        self,
        username: str,
        drawer_name: str,
        definition: dict[str, Any],
    ) -> str:
        """Save a custom drawer definition.

        Args:
            username: Username (subdirectory)
            drawer_name: Drawer name (used for filename)
            definition: YAML definition dict

        Returns:
            Relative path to saved file
        """
        # Create user directory if needed
        user_dir = self.base_path / username
        user_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in '-_' else '_' for c in drawer_name)
        filename = f"{safe_name}.yaml"
        filepath = user_dir / filename

        # Ensure author is set
        definition['author'] = username

        with open(filepath, 'w') as f:
            yaml.dump(definition, f, default_flow_style=False)

        return str(filepath.relative_to(self.base_path))

    def delete_drawer(self, relative_path: str) -> bool:
        """Delete a custom drawer file.

        Args:
            relative_path: Path relative to custom_drawers directory

        Returns:
            True if deleted, False if not found
        """
        yaml_path = self.base_path / relative_path

        if yaml_path.exists():
            yaml_path.unlink()
            return True
        return False


# Example drawer template
EXAMPLE_DRAWER_YAML = '''name: "Wave Pattern"
author: "example"
description: "Simple animated wave pattern"
created: 2025-12-06

uses:
  audio: false
  video: false
  canvas: false

settings:
  speed:
    type: float
    default: 1.0
    min: 0.1
    max: 5.0
    description: "Animation speed"

  wave_count:
    type: int
    default: 3
    min: 1
    max: 10
    description: "Number of waves"

  color_speed:
    type: float
    default: 0.5
    min: 0.0
    max: 2.0
    description: "Color cycling speed"

code: |
  def draw(width, height, ctx, settings, palette_size):
      t = ctx.time * settings['speed']

      # Create coordinate grids using meshgrid
      x = np.arange(width, dtype=np.float32)
      y = np.arange(height, dtype=np.float32)
      xx, yy = np.meshgrid(x, y)

      x_norm = xx / width
      y_norm = yy / height

      # Generate waves
      wave_count = int(settings['wave_count'])
      waves = np.sin(x_norm * wave_count * np.pi * 2 + t)
      waves = waves * np.cos(y_norm * wave_count * np.pi + t * 0.7)

      # Normalize to 0-1 range
      normalized = (waves + 1) / 2

      # Apply color cycling
      color_offset = ctx.time * settings['color_speed'] * palette_size
      indices = ((normalized * (palette_size - 1)) + color_offset).astype(np.int32)

      return indices % palette_size
'''
