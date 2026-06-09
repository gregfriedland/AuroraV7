"""Separate process for direct rpi-rgb-led-matrix output.

The hardware driver is optional and Raspberry Pi specific, so imports for
``rgbmatrix`` and Pillow stay inside the subprocess.
"""

import multiprocessing as mp
from typing import Any

import numpy as np

from .shared_frame import SharedFrame


class RgbMatrixOptionsBuilder:
    """Build rpi-rgb-led-matrix options from Aurora matrix config."""

    OPTIONAL_FIELDS = (
        "pwm_bits",
        "pwm_lsb_nanoseconds",
        "pwm_dither_bits",
        "brightness",
        "limit_refresh_rate_hz",
        "scan_mode",
        "multiplexing",
        "row_address_type",
    )

    @staticmethod
    def normalize_config(matrix_config: dict[str, Any]) -> dict[str, Any]:
        """Return normalized rgbmatrix config with V6-compatible defaults."""
        width = int(matrix_config.get("width", 192))
        height = int(matrix_config.get("height", 96))
        rgbmatrix_config = dict(matrix_config.get("rgbmatrix", {}))

        rows = int(rgbmatrix_config.get("rows", 32))
        cols = int(rgbmatrix_config.get("cols", 32))
        chain_length = int(rgbmatrix_config.get("chain_length", max(1, width // cols)))
        parallel = int(rgbmatrix_config.get("parallel", max(1, height // rows)))

        normalized = {
            "rows": rows,
            "cols": cols,
            "chain_length": chain_length,
            "parallel": parallel,
            "hardware_mapping": rgbmatrix_config.get("hardware_mapping", "regular"),
            "gpio_slowdown": int(rgbmatrix_config.get("gpio_slowdown", 2)),
            "show_refresh_rate": bool(rgbmatrix_config.get("show_refresh_rate", False)),
            "luminance_correct": bool(rgbmatrix_config.get("luminance_correct", True)),
            "swap_framerate_fraction": int(rgbmatrix_config.get("swap_framerate_fraction", 5)),
        }

        for field in RgbMatrixOptionsBuilder.OPTIONAL_FIELDS:
            value = rgbmatrix_config.get(field)
            if value is not None:
                normalized[field] = value

        drop_privileges = rgbmatrix_config.get("drop_privileges")
        if drop_privileges is not None:
            normalized["drop_privileges"] = bool(drop_privileges)

        return normalized

    @staticmethod
    def build_options(rgbmatrix_config: dict[str, Any]):
        """Build RGBMatrixOptions from normalized config."""
        from rgbmatrix import RGBMatrixOptions  # type: ignore

        options = RGBMatrixOptions()
        options.rows = int(rgbmatrix_config["rows"])
        options.cols = int(rgbmatrix_config["cols"])
        options.chain_length = int(rgbmatrix_config["chain_length"])
        options.parallel = int(rgbmatrix_config["parallel"])
        options.hardware_mapping = str(rgbmatrix_config["hardware_mapping"])
        options.gpio_slowdown = int(rgbmatrix_config["gpio_slowdown"])
        options.show_refresh_rate = bool(rgbmatrix_config["show_refresh_rate"])

        for field in RgbMatrixOptionsBuilder.OPTIONAL_FIELDS:
            if field in rgbmatrix_config:
                setattr(options, field, rgbmatrix_config[field])

        if "drop_privileges" in rgbmatrix_config:
            options.drop_privileges = rgbmatrix_config["drop_privileges"]

        return options


class RgbMatrixOutputManager:
    """Manages the rpi-rgb-led-matrix output subprocess."""

    def __init__(
        self,
        width: int,
        height: int,
        fps: int = 35,
        rgbmatrix_config: dict[str, Any] | None = None,
    ):
        self.shared_frame = SharedFrame(width, height)
        self.stop_event = mp.Event()
        self.process: mp.Process | None = None

        self.width = width
        self.height = height
        self.fps = fps
        self.rgbmatrix_config = rgbmatrix_config or {}
        self.frame_num = 0

    @staticmethod
    def output_loop(
        shared_frame: SharedFrame,
        width: int,
        height: int,
        fps: int,
        rgbmatrix_config: dict[str, Any],
        stop_event: mp.Event,
    ) -> None:
        """Read RGB frames from shared memory and display them on HUB75 panels."""
        import time

        from PIL import Image
        from rgbmatrix import RGBMatrix  # type: ignore

        options = RgbMatrixOptionsBuilder.build_options(rgbmatrix_config)
        matrix = RGBMatrix(options=options)
        matrix.luminanceCorrect = bool(rgbmatrix_config["luminance_correct"])
        canvas = matrix.CreateFrameCanvas()

        frame_time = 1.0 / fps
        last_frame_num = -1
        framerate_fraction = int(rgbmatrix_config["swap_framerate_fraction"])

        try:
            while not stop_event.is_set():
                start = time.perf_counter()
                rgb, frame_num = shared_frame.read_frame()

                if frame_num != last_frame_num:
                    last_frame_num = frame_num
                    image = Image.fromarray(np.ascontiguousarray(rgb), mode="RGB")
                    canvas.SetImage(image)
                    canvas = matrix.SwapOnVSync(canvas, framerate_fraction=framerate_fraction)

                elapsed = time.perf_counter() - start
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            matrix.Clear()

    def start(self) -> None:
        """Start the rgbmatrix output process."""
        self.process = mp.Process(
            target=RgbMatrixOutputManager.output_loop,
            args=(
                self.shared_frame,
                self.width,
                self.height,
                self.fps,
                self.rgbmatrix_config,
                self.stop_event,
            ),
            daemon=True,
        )
        self.process.start()
        print(f"[Main] Started rgbmatrix process (PID {self.process.pid})")

    def send_frame(self, rgb: np.ndarray) -> None:
        """Send frame to output process via shared memory."""
        self.frame_num += 1
        self.shared_frame.write_frame(rgb, self.frame_num)

    def stop(self) -> None:
        """Stop the rgbmatrix output process."""
        self.stop_event.set()
        if self.process:
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.terminate()
            print("[Main] Rgbmatrix process stopped")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
