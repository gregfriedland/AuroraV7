"""Core components for Aurora Web."""

from .shared_frame import SharedFrame
from .serial_process import SerialOutputManager
from .palette import Palette
from .drawer_manager import DrawerManager
from .users import UserManager, UserProfile

__all__ = [
    "SharedFrame",
    "SerialOutputManager",
    "Palette",
    "DrawerManager",
    "UserManager",
    "UserProfile",
]
