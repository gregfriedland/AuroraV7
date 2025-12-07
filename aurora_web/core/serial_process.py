"""Separate process for serial output to LED matrix.

This runs in its own process to ensure consistent frame rate
independent of main process GC or computation delays.
"""

import multiprocessing as mp
import numpy as np
import time

from .shared_frame import SharedFrame


def serial_output_loop(
    shared_frame: SharedFrame,
    device: str,
    width: int,
    height: int,
    fps: int,
    gamma: float,
    layout_ltr: bool,
    stop_event: mp.Event
) -> None:
    """Main loop for serial output process.

    Reads frames from shared memory and writes to serial at consistent rate.

    Args:
        shared_frame: Shared memory frame buffer
        device: Serial device path (e.g., /dev/ttyACM0)
        width: Frame width
        height: Frame height
        fps: Target frames per second
        gamma: Gamma correction value (e.g., 2.5)
        layout_ltr: True if first row goes left-to-right
        stop_event: Event to signal shutdown
    """
    import serial  # Import here so main process doesn't need pyserial

    # Build gamma lookup table
    gamma_lut = np.array(
        [int(255 * (i / 255) ** gamma) for i in range(256)],
        dtype=np.uint8
    )

    # Open serial port
    ser: serial.Serial | None = None
    if device:
        try:
            ser = serial.Serial(device, 115200)
            print(f"[Serial Process] Opened {device}")
        except Exception as e:
            print(f"[Serial Process] Failed to open {device}: {e}")
            return

    frame_time = 1.0 / fps
    last_frame_num = -1

    try:
        while not stop_event.is_set():
            start = time.perf_counter()

            # Read frame from shared memory
            rgb, frame_num = shared_frame.read_frame()

            # Only send if new frame
            if frame_num != last_frame_num:
                last_frame_num = frame_num

                # Apply gamma correction
                rgb = gamma_lut[rgb]

                # Apply snake pattern (alternate rows reversed)
                for y in range(height):
                    should_reverse = (y % 2 == 1) if layout_ltr else (y % 2 == 0)
                    if should_reverse:
                        rgb[y, :, :] = rgb[y, ::-1, :]

                # Cap at 254 (255 is delimiter), flatten, add delimiter
                data = np.clip(rgb.flatten(), 0, 254).astype(np.uint8)

                if ser:
                    ser.write(bytes(data) + b'\xff')

            # Maintain frame rate
            elapsed = time.perf_counter() - start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        if ser:
            ser.close()
            print("[Serial Process] Closed serial port")


class SerialOutputManager:
    """Manages the serial output subprocess."""

    def __init__(
        self,
        device: str,
        width: int,
        height: int,
        fps: int = 40,
        gamma: float = 2.5,
        layout_ltr: bool = True
    ):
        """Initialize serial output manager.

        Args:
            device: Serial device path
            width: Frame width
            height: Frame height
            fps: Target FPS for serial output
            gamma: Gamma correction value
            layout_ltr: True if first LED row goes left-to-right
        """
        self.shared_frame = SharedFrame(width, height)
        self.stop_event = mp.Event()
        self.process: mp.Process | None = None

        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.gamma = gamma
        self.layout_ltr = layout_ltr
        self.frame_num = 0

    def start(self) -> None:
        """Start the serial output process."""
        self.process = mp.Process(
            target=serial_output_loop,
            args=(
                self.shared_frame,
                self.device,
                self.width,
                self.height,
                self.fps,
                self.gamma,
                self.layout_ltr,
                self.stop_event
            ),
            daemon=True
        )
        self.process.start()
        print(f"[Main] Started serial process (PID {self.process.pid})")

    def send_frame(self, rgb: np.ndarray) -> None:
        """Send frame to serial process via shared memory.

        Args:
            rgb: RGB frame array, shape (height, width, 3)
        """
        self.frame_num += 1
        self.shared_frame.write_frame(rgb, self.frame_num)

    def stop(self) -> None:
        """Stop the serial output process."""
        self.stop_event.set()
        if self.process:
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.terminate()
            print("[Main] Serial process stopped")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
