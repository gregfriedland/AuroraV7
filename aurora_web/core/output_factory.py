"""Output driver factory for Aurora Web."""

from typing import Protocol

import numpy as np

from aurora_web.core.rgbmatrix_process import RgbMatrixOptionsBuilder, RgbMatrixOutputManager
from aurora_web.core.serial_process import SerialOutputManager


class OutputManager(Protocol):
    """Common interface for hardware output managers."""

    def start(self) -> None:
        """Start hardware output."""

    def send_frame(self, rgb: np.ndarray) -> None:
        """Send one RGB frame to hardware output."""

    def stop(self) -> None:
        """Stop hardware output."""


class OutputManagerFactory:
    """Create output managers from Aurora matrix config."""

    @staticmethod
    def create(matrix_config: dict) -> OutputManager:
        """Create the configured output manager."""
        driver = str(matrix_config.get("output_driver", matrix_config.get("driver", "serial"))).lower()
        if "matrix" in matrix_config and "output_driver" not in matrix_config and "driver" not in matrix_config:
            legacy_matrix = str(matrix_config["matrix"]).lower()
            if legacy_matrix in ("hzellerrpi", "rgbmatrix"):
                driver = "rgbmatrix"
            elif legacy_matrix == "serial":
                driver = "serial"

        width = int(matrix_config.get("width", 32))
        height = int(matrix_config.get("height", 18))
        fps = int(matrix_config.get("fps", 40))

        if driver == "serial":
            serial_config = matrix_config.get("serial", {})
            return SerialOutputManager(
                device=serial_config.get("device", matrix_config.get("serial_device", "/dev/ttyACM0")),
                width=width,
                height=height,
                fps=fps,
                gamma=float(matrix_config.get("gamma", 2.5)),
                layout_ltr=bool(serial_config.get(
                    "layout_left_to_right",
                    matrix_config.get("layout_left_to_right", True),
                )),
            )

        if driver in ("rgbmatrix", "hzellerrpi"):
            return RgbMatrixOutputManager(
                width=width,
                height=height,
                fps=fps,
                rgbmatrix_config=RgbMatrixOptionsBuilder.normalize_config(matrix_config),
            )

        raise ValueError(f"Unknown output driver: {driver}")
