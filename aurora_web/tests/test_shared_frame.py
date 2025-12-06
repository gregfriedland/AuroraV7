"""Tests for the SharedFrame class."""

import numpy as np
import pytest

from aurora_web.core.shared_frame import SharedFrame


class TestSharedFrame:
    """Tests for SharedFrame class."""

    def test_initialization(self):
        """SharedFrame should initialize with correct dimensions."""
        frame = SharedFrame(32, 18)
        assert frame.width == 32
        assert frame.height == 18
        assert frame.frame_size == 32 * 18 * 3

    def test_write_and_read_frame(self):
        """write_frame and read_frame should round-trip data."""
        frame = SharedFrame(32, 18)

        # Create test RGB data
        rgb = np.random.randint(0, 255, (18, 32, 3), dtype=np.uint8)
        frame_num = 42

        frame.write_frame(rgb, frame_num)
        read_rgb, read_num = frame.read_frame()

        np.testing.assert_array_equal(read_rgb, rgb)
        assert read_num == frame_num

    def test_frame_num_updates(self):
        """Frame number should update on each write."""
        frame = SharedFrame(32, 18)
        rgb = np.zeros((18, 32, 3), dtype=np.uint8)

        frame.write_frame(rgb, 1)
        _, num1 = frame.read_frame()
        assert num1 == 1

        frame.write_frame(rgb, 2)
        _, num2 = frame.read_frame()
        assert num2 == 2

    def test_initial_frame_num(self):
        """Initial frame number should be 0."""
        frame = SharedFrame(32, 18)
        _, num = frame.read_frame()
        assert num == 0

    def test_read_returns_copy(self):
        """read_frame should return a copy, not view of shared memory."""
        frame = SharedFrame(32, 18)
        rgb = np.full((18, 32, 3), 100, dtype=np.uint8)
        frame.write_frame(rgb, 1)

        read_rgb, _ = frame.read_frame()
        read_rgb[0, 0, 0] = 200  # Modify the returned array

        # Original data in shared memory should be unchanged
        read_again, _ = frame.read_frame()
        assert read_again[0, 0, 0] == 100

    def test_different_sizes(self):
        """SharedFrame should work with different sizes."""
        for width, height in [(10, 10), (64, 64), (100, 50)]:
            frame = SharedFrame(width, height)
            rgb = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)

            frame.write_frame(rgb, 1)
            read_rgb, _ = frame.read_frame()

            np.testing.assert_array_equal(read_rgb, rgb)

    def test_multiple_writes(self):
        """Multiple writes should overwrite previous data."""
        frame = SharedFrame(32, 18)

        # Write red frame
        red = np.zeros((18, 32, 3), dtype=np.uint8)
        red[:, :, 0] = 255
        frame.write_frame(red, 1)

        # Write green frame
        green = np.zeros((18, 32, 3), dtype=np.uint8)
        green[:, :, 1] = 255
        frame.write_frame(green, 2)

        read_rgb, num = frame.read_frame()

        # Should be green, not red
        assert num == 2
        assert read_rgb[0, 0, 0] == 0   # No red
        assert read_rgb[0, 0, 1] == 255  # Green
        assert read_rgb[0, 0, 2] == 0   # No blue

    def test_preserves_all_channels(self):
        """All RGB channels should be preserved."""
        frame = SharedFrame(32, 18)

        # Create frame with distinct values in each channel
        rgb = np.zeros((18, 32, 3), dtype=np.uint8)
        rgb[:, :, 0] = 50   # R
        rgb[:, :, 1] = 100  # G
        rgb[:, :, 2] = 150  # B

        frame.write_frame(rgb, 1)
        read_rgb, _ = frame.read_frame()

        assert read_rgb[0, 0, 0] == 50
        assert read_rgb[0, 0, 1] == 100
        assert read_rgb[0, 0, 2] == 150
