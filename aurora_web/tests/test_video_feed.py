"""Tests for VideoFeed class."""

import numpy as np
import pytest
import asyncio
import time
import cv2

from aurora_web.inputs.video_feed import VideoFeed, VideoInput, MockVideoFeed


class TestVideoInput:
    """Tests for VideoInput dataclass."""

    def test_default_values(self):
        """VideoInput should have sensible defaults."""
        video = VideoInput()
        assert video.frame is None
        assert video.motion_amount == 0.0
        assert video.motion_map is None
        assert video.light_level == 0.5
        assert video.dominant_color is None
        assert video.faces is None

    def test_custom_values(self):
        """VideoInput should accept custom values."""
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        motion_map = np.ones((240, 320), dtype=np.float32) * 0.5
        video = VideoInput(
            frame=frame,
            motion_amount=0.3,
            motion_map=motion_map,
            light_level=0.8,
            dominant_color=(255, 128, 64),
            faces=[(10, 20, 50, 50)],
        )
        assert video.frame is not None
        assert video.frame.shape == (240, 320, 3)
        assert video.motion_amount == 0.3
        assert video.motion_map is not None
        assert video.light_level == 0.8
        assert video.dominant_color == (255, 128, 64)
        assert len(video.faces) == 1


class TestVideoFeed:
    """Tests for VideoFeed class."""

    def test_initialization(self):
        """VideoFeed should initialize with defaults."""
        feed = VideoFeed()
        assert feed.device == 0
        assert feed.width == 320
        assert feed.height == 240
        assert feed.fps == 30
        assert feed.motion_threshold == 0.02
        assert feed.enable_face_detection is False
        assert feed.rotation == 0
        assert feed.is_running is False

    def test_custom_initialization(self):
        """VideoFeed should accept custom parameters."""
        feed = VideoFeed(
            device=1,
            width=640,
            height=480,
            fps=60,
            motion_threshold=0.05,
            enable_face_detection=True,
            rotation=180,
        )
        assert feed.device == 1
        assert feed.width == 640
        assert feed.height == 480
        assert feed.fps == 60
        assert feed.motion_threshold == 0.05
        assert feed.enable_face_detection is True
        assert feed.rotation == 180

    def test_get_input_when_not_running(self):
        """get_input should return empty VideoInput when not running."""
        feed = VideoFeed()
        result = feed.get_input()
        assert isinstance(result, VideoInput)
        assert result.frame is None
        assert result.motion_amount == 0.0

    def test_start_without_picamera2_logs_warning(self):
        """start() should log warning and not crash when picamera2 unavailable."""
        async def run_test():
            feed = VideoFeed()
            await feed.start()
            # On macOS/non-Pi, picamera2 won't be available
            # Feed should gracefully not start
            assert not feed.is_running

        asyncio.run(run_test())

    def test_analyze_light_level(self):
        """_analyze should compute light level from frame."""
        feed = VideoFeed()
        feed.prev_gray = None  # Reset

        brightness = 128
        frame = np.full((240, 320, 3), brightness, dtype=np.uint8)
        feed._analyze(frame)

        assert 0.45 < feed.light_level < 0.55

    def test_analyze_light_level_dark(self):
        """_analyze should detect dark frames."""
        feed = VideoFeed()
        feed.prev_gray = None

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        feed._analyze(frame)

        assert feed.light_level < 0.1

    def test_analyze_light_level_bright(self):
        """_analyze should detect bright frames."""
        feed = VideoFeed()
        feed.prev_gray = None

        frame = np.full((240, 320, 3), 255, dtype=np.uint8)
        feed._analyze(frame)

        assert feed.light_level > 0.9

    def test_analyze_motion_detection(self):
        """_analyze should detect motion between frames."""
        feed = VideoFeed(motion_threshold=0.01)

        frame1 = np.zeros((240, 320, 3), dtype=np.uint8)
        feed._analyze(frame1)
        assert feed.motion_amount == 0.0

        frame2 = np.full((240, 320, 3), 128, dtype=np.uint8)
        feed._analyze(frame2)
        assert feed.motion_amount > 0.0
        assert feed.motion_map is not None
        assert feed.motion_map.shape == (240, 320)

    def test_analyze_no_motion_same_frame(self):
        """_analyze should detect no motion for identical frames."""
        feed = VideoFeed()

        frame = np.full((240, 320, 3), 128, dtype=np.uint8)
        feed._analyze(frame)
        feed._analyze(frame.copy())

        assert feed.motion_amount == 0.0

    def test_analyze_dominant_color(self):
        """_analyze should compute dominant color."""
        feed = VideoFeed()

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[:, :, 0] = 255  # Blue channel in BGR

        feed._analyze(frame)

        assert feed.dominant_color is not None
        r, g, b = feed.dominant_color
        assert b > r and b > g

    def test_analyze_stores_rgb_frame(self):
        """_analyze should store frame in RGB format."""
        feed = VideoFeed()

        frame_bgr = np.zeros((240, 320, 3), dtype=np.uint8)
        frame_bgr[:, :, 2] = 255  # Red channel in BGR

        feed._analyze(frame_bgr)

        assert feed.frame is not None
        assert feed.frame.shape == (240, 320, 3)
        assert np.mean(feed.frame[:, :, 0]) > 200  # Red channel high
        assert np.mean(feed.frame[:, :, 2]) < 50   # Blue channel low

    def test_get_input_returns_copy(self):
        """get_input should return copies of arrays."""
        feed = VideoFeed()

        frame = np.full((240, 320, 3), 128, dtype=np.uint8)
        feed._analyze(frame)

        result1 = feed.get_input()
        result2 = feed.get_input()

        assert np.array_equal(result1.frame, result2.frame)
        assert result1.frame is not result2.frame


class TestVideoFeedRotation:
    """Tests for VideoFeed rotation."""

    def test_rotation_0_no_change(self):
        """rotation=0 should not modify the frame."""
        feed = VideoFeed(rotation=0)

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[0, 0, 0] = 255  # top-left pixel, blue channel BGR
        feed._analyze(frame.copy())

        # Stored as RGB: top-left should have blue=255
        assert feed.frame[0, 0, 2] == 255

    def test_rotation_180_flips(self):
        """rotation=180 should flip the frame."""
        feed = VideoFeed(rotation=180)

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[0, 0, :] = 200

        feed._analyze(frame.copy())

        assert feed.frame[0, 0, 0] == 0  # top-left is now black
        assert feed.frame[239, 319, 0] == 200  # bottom-right has the marker

    def test_rotation_90(self):
        """rotation=90 should rotate clockwise."""
        feed = VideoFeed(rotation=90)

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[0, 0, :] = 200

        feed._analyze(frame.copy())

        # After 90° CW, frame dimensions swap
        assert feed.frame.shape == (320, 240, 3)
        assert feed.frame[0, 239, 0] == 200

    def test_rotation_270(self):
        """rotation=270 should rotate counter-clockwise."""
        feed = VideoFeed(rotation=270)

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[0, 0, :] = 200

        feed._analyze(frame.copy())

        assert feed.frame.shape == (320, 240, 3)
        assert feed.frame[319, 0, 0] == 200


class TestMockVideoFeed:
    """Tests for MockVideoFeed class."""

    def test_initialization(self):
        """MockVideoFeed should initialize with defaults."""
        feed = MockVideoFeed()
        assert feed.width == 320
        assert feed.height == 240
        assert feed.simulated_motion == 0.1
        assert feed.simulated_light == 0.5
        assert not feed.is_running

    def test_custom_initialization(self):
        """MockVideoFeed should accept custom parameters."""
        feed = MockVideoFeed(
            width=640,
            height=480,
            simulated_motion=0.3,
            simulated_light=0.8,
        )
        assert feed.width == 640
        assert feed.height == 480
        assert feed.simulated_motion == 0.3
        assert feed.simulated_light == 0.8

    def test_start_stop(self):
        """MockVideoFeed should start and stop."""
        async def run_test():
            feed = MockVideoFeed()
            await feed.start()
            assert feed.is_running
            await feed.stop()
            assert not feed.is_running

        asyncio.run(run_test())

    def test_get_input_when_stopped(self):
        """get_input should return empty VideoInput when stopped."""
        feed = MockVideoFeed()
        result = feed.get_input()
        assert result.frame is None
        assert result.motion_amount == 0.0

    def test_get_input_when_running(self):
        """get_input should return valid VideoInput when running."""
        async def run_test():
            feed = MockVideoFeed()
            await feed.start()

            result = feed.get_input()
            assert result.frame is not None
            assert result.frame.shape == (240, 320, 3)
            assert 0 <= result.motion_amount <= 1
            assert 0 <= result.light_level <= 1
            assert result.motion_map is not None
            assert result.dominant_color is not None

            await feed.stop()

        asyncio.run(run_test())

    def test_motion_varies_over_time(self):
        """MockVideoFeed motion should vary over time."""
        async def run_test():
            feed = MockVideoFeed(simulated_motion=0.5)
            await feed.start()

            motions = []
            for _ in range(10):
                result = feed.get_input()
                motions.append(result.motion_amount)
                time.sleep(0.1)

            await feed.stop()

            assert len(set(round(m, 3) for m in motions)) > 1

        asyncio.run(run_test())

    def test_light_level_varies_over_time(self):
        """MockVideoFeed light level should vary over time."""
        async def run_test():
            feed = MockVideoFeed(simulated_light=0.5)
            await feed.start()

            lights = []
            for _ in range(10):
                result = feed.get_input()
                lights.append(result.light_level)
                time.sleep(0.1)

            await feed.stop()

            assert len(set(round(l, 3) for l in lights)) > 1

        asyncio.run(run_test())

    def test_frame_has_correct_shape(self):
        """MockVideoFeed frame should have correct dimensions."""
        async def run_test():
            feed = MockVideoFeed(width=100, height=50)
            await feed.start()

            result = feed.get_input()
            assert result.frame.shape == (50, 100, 3)
            assert result.motion_map.shape == (50, 100)

            await feed.stop()

        asyncio.run(run_test())

    def test_values_in_valid_range(self):
        """MockVideoFeed values should be in valid ranges."""
        async def run_test():
            feed = MockVideoFeed()
            await feed.start()

            for _ in range(20):
                result = feed.get_input()
                assert 0 <= result.motion_amount <= 1
                assert 0 <= result.light_level <= 1
                assert np.all(result.motion_map >= 0)
                assert np.all(result.motion_map <= 1)
                assert np.all(result.frame >= 0)
                assert np.all(result.frame <= 255)
                time.sleep(0.05)

            await feed.stop()

        asyncio.run(run_test())

    def test_dominant_color_is_valid_rgb(self):
        """MockVideoFeed dominant color should be valid RGB."""
        async def run_test():
            feed = MockVideoFeed()
            await feed.start()

            result = feed.get_input()
            assert result.dominant_color is not None
            r, g, b = result.dominant_color
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255

            await feed.stop()

        asyncio.run(run_test())
