"""Shared memory frame buffer between main and serial processes."""

import ctypes
import multiprocessing as mp
import numpy as np
from typing import Tuple


class SharedFrame:
    """Shared memory frame buffer for zero-copy frame transfer between processes.

    Uses multiprocessing.Array for the raw pixel data and Value for frame metadata.
    """

    def __init__(self, width: int, height: int):
        """Initialize shared frame buffer.

        Args:
            width: Frame width in pixels
            height: Frame height in pixels
        """
        self.width = width
        self.height = height
        self.frame_size = width * height * 3  # RGB

        # Shared memory: RGB frame data
        self.shared_array = mp.Array('B', self.frame_size)  # 'B' = unsigned char
        self.lock = mp.Lock()
        self.frame_num = mp.Value('L', 0)  # Unsigned long for frame counter

    def write_frame(self, rgb: np.ndarray, frame_num: int) -> None:
        """Write frame from main process.

        Args:
            rgb: RGB frame data, shape (height, width, 3), dtype uint8
            frame_num: Frame number for tracking
        """
        flat = rgb.flatten().astype(np.uint8)
        with self.lock:
            # Bulk copy using ctypes memmove - no Python loop
            ctypes.memmove(self.shared_array.get_obj(), flat.ctypes.data, self.frame_size)
            self.frame_num.value = frame_num

    def read_frame(self) -> Tuple[np.ndarray, int]:
        """Read frame from serial process.

        Returns:
            Tuple of (rgb frame array, frame number)
        """
        with self.lock:
            data = bytes(self.shared_array[:])
            frame_num = self.frame_num.value
        return (
            np.frombuffer(data, dtype=np.uint8).reshape(self.height, self.width, 3).copy(),
            frame_num
        )
