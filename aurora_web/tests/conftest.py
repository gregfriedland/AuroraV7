"""Pytest configuration and fixtures."""

import pytest
import sys
from pathlib import Path

# Add aurora_web to path for imports
aurora_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(aurora_root))
