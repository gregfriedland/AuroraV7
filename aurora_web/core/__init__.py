"""Core components for Aurora Web."""

from .shared_frame import SharedFrame
from .serial_process import SerialOutputManager
from .rgbmatrix_process import RgbMatrixOutputManager
from .output_factory import OutputManagerFactory
from .find_beats import ExternalBeatFeed
from .palette import Palette
from .drawer_manager import DrawerManager
from .users import UserManager, UserProfile

__all__ = [
    "SharedFrame",
    "SerialOutputManager",
    "RgbMatrixOutputManager",
    "OutputManagerFactory",
    "ExternalBeatFeed",
    "Palette",
    "DrawerManager",
    "UserManager",
    "UserProfile",
]
