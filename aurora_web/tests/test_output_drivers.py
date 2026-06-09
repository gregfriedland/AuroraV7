"""Tests for output driver selection and rgbmatrix configuration."""

import sys
import types

from aurora_web.core.output_factory import OutputManagerFactory
from aurora_web.core.rgbmatrix_process import RgbMatrixOptionsBuilder, RgbMatrixOutputManager
from aurora_web.core.serial_process import SerialOutputManager


class TestOutputManagerFactory:
    """Tests for output manager selection."""

    def test_default_driver_is_serial(self):
        manager = OutputManagerFactory.create({
            "width": 32,
            "height": 18,
            "serial_device": "/dev/test",
        })

        assert isinstance(manager, SerialOutputManager)
        assert manager.device == "/dev/test"

    def test_serial_driver_uses_nested_config_when_present(self):
        manager = OutputManagerFactory.create({
            "width": 64,
            "height": 32,
            "output_driver": "serial",
            "serial": {
                "device": "/dev/nested",
                "layout_left_to_right": False,
            },
        })

        assert isinstance(manager, SerialOutputManager)
        assert manager.device == "/dev/nested"
        assert manager.layout_ltr is False

    def test_v6_hzeller_matrix_selects_rgbmatrix(self):
        manager = OutputManagerFactory.create({
            "width": 192,
            "height": 96,
            "fps": 35,
            "matrix": "HzellerRpi",
        })

        assert isinstance(manager, RgbMatrixOutputManager)
        assert manager.rgbmatrix_config["rows"] == 32
        assert manager.rgbmatrix_config["cols"] == 32
        assert manager.rgbmatrix_config["chain_length"] == 6
        assert manager.rgbmatrix_config["parallel"] == 3


class TestRgbMatrixOptionsBuilder:
    """Tests for rpi-rgb-led-matrix option mapping."""

    def test_normalize_config_uses_v6_compatible_defaults(self):
        config = RgbMatrixOptionsBuilder.normalize_config({
            "width": 192,
            "height": 96,
            "rgbmatrix": {},
        })

        assert config["rows"] == 32
        assert config["cols"] == 32
        assert config["chain_length"] == 6
        assert config["parallel"] == 3
        assert config["hardware_mapping"] == "regular"
        assert config["gpio_slowdown"] == 2
        assert config["luminance_correct"] is True

    def test_normalize_config_honors_overrides(self):
        config = RgbMatrixOptionsBuilder.normalize_config({
            "width": 128,
            "height": 64,
            "rgbmatrix": {
                "rows": 64,
                "cols": 64,
                "chain_length": 2,
                "parallel": 1,
                "hardware_mapping": "adafruit-hat",
                "gpio_slowdown": 4,
                "brightness": 70,
                "pwm_bits": 7,
                "drop_privileges": False,
            },
        })

        assert config["rows"] == 64
        assert config["cols"] == 64
        assert config["chain_length"] == 2
        assert config["parallel"] == 1
        assert config["hardware_mapping"] == "adafruit-hat"
        assert config["gpio_slowdown"] == 4
        assert config["brightness"] == 70
        assert config["pwm_bits"] == 7
        assert config["drop_privileges"] is False

    def test_build_options_sets_rgbmatrix_options(self, monkeypatch):
        class FakeOptions:
            pass

        fake_module = types.SimpleNamespace(RGBMatrixOptions=FakeOptions)
        monkeypatch.setitem(sys.modules, "rgbmatrix", fake_module)

        options = RgbMatrixOptionsBuilder.build_options({
            "rows": 32,
            "cols": 64,
            "chain_length": 3,
            "parallel": 2,
            "hardware_mapping": "regular",
            "gpio_slowdown": 2,
            "show_refresh_rate": True,
            "brightness": 80,
            "pwm_dither_bits": 1,
            "drop_privileges": False,
        })

        assert options.rows == 32
        assert options.cols == 64
        assert options.chain_length == 3
        assert options.parallel == 2
        assert options.hardware_mapping == "regular"
        assert options.gpio_slowdown == 2
        assert options.show_refresh_rate is True
        assert options.brightness == 80
        assert options.pwm_dither_bits == 1
        assert options.drop_privileges is False
