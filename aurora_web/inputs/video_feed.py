"""Video feed for motion detection and light level analysis."""

import logging
import numpy as np
import asyncio
import time
import cv2
from dataclasses import dataclass
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


@dataclass
class VideoInput:
    """Video analysis data passed to drawers."""
    frame: np.ndarray | None = None          # Current camera frame (RGB, height x width x 3)
    motion_amount: float = 0.0                  # 0.0-1.0 overall motion level
    motion_map: np.ndarray | None = None     # Per-pixel motion intensity (height x width)
    light_level: float = 0.5                    # 0.0-1.0 average brightness
    dominant_color: tuple[int, int, int | None] = None  # Most common color (R, G, B)
    faces: list[tuple[int, int, int, int | None]] = None  # Detected face regions (x, y, w, h)


def _has_picamera2() -> bool:
    """Check if picamera2 is available (Raspberry Pi)."""
    try:
        import picamera2  # noqa: F401
        return True
    except ImportError:
        return False


class VideoFeed:
    """Captures and analyzes video for motion and light levels.

    Uses picamera2 (Raspberry Pi). If picamera2 is not available,
    the feed will not start and the camera pattern will be disabled.
    """

    def __init__(
        self,
        device: int = 0,
        width: int = 320,
        height: int = 240,
        fps: int = 30,
        motion_threshold: float = 0.02,
        enable_face_detection: bool = False,
        rotation: int = 0,
    ):
        """Initialize video feed.

        Args:
            device: Camera device index (0 for default camera)
            width: Capture width
            height: Capture height
            fps: Target frames per second
            motion_threshold: Minimum motion to register (0-1)
            enable_face_detection: Whether to detect faces (requires haarcascade)
            rotation: Rotate captured frames (0, 90, 180, or 270 degrees)
        """
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.motion_threshold = motion_threshold
        self.enable_face_detection = enable_face_detection
        self.rotation = rotation

        # State
        self.frame: np.ndarray | None = None
        self.prev_gray: np.ndarray | None = None
        self.motion_amount: float = 0.0
        self.motion_map: np.ndarray | None = None
        self.light_level: float = 0.5
        self.dominant_color: tuple[int, int, int | None] = None
        self.faces: list[tuple[int, int, int, int | None]] = None

        # Motion history for smoothing
        self._motion_history: list[float] = []

        # Camera backend
        self._picam: object | None = None
        self._face_detector = None

        # Async control
        self._running: bool = False
        self._task: asyncio.Task | None = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def start(self) -> None:
        """Start video capture and analysis."""
        if self._running:
            return

        if not _has_picamera2():
            logger.warning("picamera2 not available — camera pattern disabled")
            return

        self._running = True

        loop = asyncio.get_event_loop()
        opened = await loop.run_in_executor(self._executor, self._open_camera)

        if not opened:
            logger.warning("Failed to open camera device %d — camera pattern disabled",
                           self.device)
            self._running = False
            return

        # Load face detector if needed (YuNet DNN — rotation-invariant)
        if self.enable_face_detection:
            try:
                model_path = str(Path(__file__).parent.parent / "models" / "face_detection_yunet_2023mar.onnx")
                self._face_detector = cv2.FaceDetectorYN.create(
                    model_path,
                    "",
                    (self.width, self.height),
                    score_threshold=0.5,
                    nms_threshold=0.3,
                    top_k=10,
                )
                print("[VideoFeed] Face detection enabled (YuNet)")
            except Exception as e:
                print(f"[VideoFeed] Face detection unavailable: {e}")
                self._face_detector = None

        self._task = asyncio.create_task(self._capture_loop())
        logger.info("VideoFeed started — device %d at %dx%d (rotation=%d°)",
                     self.device, self.width, self.height, self.rotation)

    def _open_camera(self) -> bool:
        """Open camera with picamera2."""
        try:
            from picamera2 import Picamera2
            self._picam = Picamera2(self.device)
            config = self._picam.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                controls={"FrameRate": self.fps},
            )
            self._picam.configure(config)
            self._picam.start()
            return True
        except Exception as e:
            logger.warning("picamera2 open failed: %s", e)
            self._picam = None
            return False

    async def _capture_loop(self) -> None:
        """Main capture loop."""
        frame_time = 1.0 / self.fps
        loop = asyncio.get_event_loop()

        try:
            while self._running:
                start = time.perf_counter()

                frame = await loop.run_in_executor(
                    self._executor,
                    self._read_frame
                )

                if frame is not None:
                    self._analyze(frame)

                # Maintain target FPS
                elapsed = time.perf_counter() - start
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0)  # Yield to other tasks

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Capture error: %s", e)

    def _read_frame(self) -> np.ndarray | None:
        """Read frame from picamera2 (runs in thread pool).

        Returns:
            BGR frame for analysis, or None on failure.
        """
        if self._picam is None:
            return None
        try:
            # picamera2 returns RGB directly
            rgb = self._picam.capture_array()
            # Convert to BGR for _analyze() compatibility
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception:
            return None

    def _analyze(self, frame: np.ndarray) -> None:
        """Analyze frame for motion, light level, and optional features.

        Args:
            frame: BGR frame from camera
        """
        # Apply rotation
        if self.rotation == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotation == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotation == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Convert to RGB for storage
        self.frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Convert to grayscale for analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Light level (average brightness)
        self.light_level = float(np.mean(gray)) / 255.0

        # Motion detection
        if self.prev_gray is not None:
            # Compute absolute difference
            diff = cv2.absdiff(gray, self.prev_gray)
            self.motion_map = diff.astype(np.float32) / 255.0

            # Apply threshold to reduce noise
            motion_binary = (self.motion_map > self.motion_threshold).astype(np.float32)
            raw_motion = float(np.mean(motion_binary))

            # Smooth motion with history
            self._motion_history.append(raw_motion)
            if len(self._motion_history) > 10:  # ~0.33s at 30fps
                self._motion_history.pop(0)
            self.motion_amount = float(np.mean(self._motion_history))
        else:
            self.motion_map = np.zeros((gray.shape[0], gray.shape[1]), dtype=np.float32)
            self.motion_amount = 0.0

        self.prev_gray = gray.copy()

        # Dominant color (sample center region for efficiency)
        h, w = frame.shape[:2]
        center_region = frame[h//4:3*h//4, w//4:3*w//4]
        avg_color = np.mean(center_region, axis=(0, 1)).astype(int)
        # Convert BGR to RGB
        self.dominant_color = (int(avg_color[2]), int(avg_color[1]), int(avg_color[0]))

        # Face detection (YuNet DNN, run every 5th frame)
        if self._face_detector is not None:
            if not hasattr(self, '_face_frame_count'):
                self._face_frame_count = 0
            self._face_frame_count += 1

            if self._face_frame_count >= 5:
                self._face_frame_count = 0
                _, raw_faces = self._face_detector.detect(frame)
                if raw_faces is not None:
                    # YuNet returns [x, y, w, h, ...landmarks, score] per row
                    self.faces = [(int(r[0]), int(r[1]), int(r[2]), int(r[3]))
                                  for r in raw_faces]
                else:
                    self.faces = []
                if not hasattr(self, '_face_log_count'):
                    self._face_log_count = 0
                self._face_log_count += 1
                if self._face_log_count <= 5 or (self.faces and self._face_log_count % 30 == 0):
                    print(f"[VideoFeed] Face detect: {len(self.faces)} faces {self.faces}")

    def get_input(self) -> VideoInput:
        """Get current video input state for drawers.

        Returns:
            VideoInput dataclass with current video state
        """
        return VideoInput(
            frame=self.frame.copy() if self.frame is not None else None,
            motion_amount=self.motion_amount,
            motion_map=self.motion_map.copy() if self.motion_map is not None else None,
            light_level=self.light_level,
            dominant_color=self.dominant_color,
            faces=self.faces.copy() if self.faces else None,
        )

    async def stop(self) -> None:
        """Stop video capture."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._picam is not None:
            try:
                self._picam.stop()
                self._picam.close()
            except Exception:
                pass
            self._picam = None

        self._executor.shutdown(wait=False)
        logger.info("VideoFeed stopped")

    @property
    def is_running(self) -> bool:
        """Check if video feed is running."""
        return self._running and self._picam is not None


class MockVideoFeed:
    """Mock video feed for testing without actual camera input.

    Generates synthetic motion and light level data.
    """

    def __init__(
        self,
        width: int = 320,
        height: int = 240,
        simulated_motion: float = 0.1,
        simulated_light: float = 0.5,
    ):
        """Initialize mock video feed.

        Args:
            width: Simulated frame width
            height: Simulated frame height
            simulated_motion: Base motion level (0-1)
            simulated_light: Base light level (0-1)
        """
        self.width = width
        self.height = height
        self.simulated_motion = simulated_motion
        self.simulated_light = simulated_light

        self._running = False
        self._start_time = 0.0

    async def start(self) -> None:
        """Start mock video feed."""
        self._running = True
        self._start_time = time.time()
        print(f"[MockVideoFeed] Started - {self.width}x{self.height}")

    async def stop(self) -> None:
        """Stop mock video feed."""
        self._running = False
        print("[MockVideoFeed] Stopped")

    def get_input(self) -> VideoInput:
        """Get simulated video input."""
        if not self._running:
            return VideoInput()

        t = time.time() - self._start_time

        # Simulate varying motion (sine wave)
        motion = self.simulated_motion + 0.1 * np.sin(t * 0.5)
        motion = float(np.clip(motion, 0, 1))

        # Simulate varying light (slower sine wave)
        light = self.simulated_light + 0.2 * np.sin(t * 0.2)
        light = float(np.clip(light, 0, 1))

        # Generate fake frame with gradient
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        for y in range(self.height):
            for x in range(self.width):
                # Simple gradient pattern
                r = int((x / self.width) * 255)
                g = int((y / self.height) * 255)
                b = int(((x + y) / (self.width + self.height)) * 255 * light)
                frame[y, x] = [r, g, b]

        # Generate motion map with some random noise
        motion_map = np.random.rand(self.height, self.width).astype(np.float32) * motion

        # Simulate dominant color based on time
        hue = (t * 30) % 360
        # Simple HSV to RGB for dominant color
        c = int(255 * light)
        if hue < 60:
            dominant = (c, int(c * hue / 60), 0)
        elif hue < 120:
            dominant = (int(c * (120 - hue) / 60), c, 0)
        elif hue < 180:
            dominant = (0, c, int(c * (hue - 120) / 60))
        elif hue < 240:
            dominant = (0, int(c * (240 - hue) / 60), c)
        elif hue < 300:
            dominant = (int(c * (hue - 240) / 60), 0, c)
        else:
            dominant = (c, 0, int(c * (360 - hue) / 60))

        return VideoInput(
            frame=frame,
            motion_amount=motion,
            motion_map=motion_map,
            light_level=light,
            dominant_color=dominant,
            faces=None,
        )

    @property
    def is_running(self) -> bool:
        return self._running
