"""Video feed for motion detection and light level analysis."""

import numpy as np
import asyncio
import time
import cv2
from dataclasses import dataclass, field

from concurrent.futures import ThreadPoolExecutor


@dataclass
class VideoInput:
    """Video analysis data passed to drawers."""
    frame: np.ndarray | None = None          # Current camera frame (RGB, height x width x 3)
    motion_amount: float = 0.0                  # 0.0-1.0 overall motion level
    motion_map: np.ndarray | None = None     # Per-pixel motion intensity (height x width)
    light_level: float = 0.5                    # 0.0-1.0 average brightness
    dominant_color: tuple[int, int, int | None] = None  # Most common color (R, G, B)
    faces: list[tuple[int, int, int, int | None]] = None  # Detected face regions (x, y, w, h)


class VideoFeed:
    """Captures and analyzes video for motion and light levels.

    Uses OpenCV to capture from camera and perform real-time analysis
    including motion detection, light level, and optional face detection.
    """

    def __init__(
        self,
        device: int = 0,
        width: int = 320,
        height: int = 240,
        fps: int = 30,
        motion_threshold: float = 0.02,
        enable_face_detection: bool = False,
    ):
        """Initialize video feed.

        Args:
            device: Camera device index (0 for default camera)
            width: Capture width
            height: Capture height
            fps: Target frames per second
            motion_threshold: Minimum motion to register (0-1)
            enable_face_detection: Whether to detect faces (requires haarcascade)
        """
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.motion_threshold = motion_threshold
        self.enable_face_detection = enable_face_detection

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

        # OpenCV objects
        self._cap: cv2.VideoCapture | None = None
        self._face_cascade = None

        # Async control
        self._running: bool = False
        self._task: asyncio.Task | None = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def start(self) -> None:
        """Start video capture and analysis."""
        if self._running:
            return

        self._running = True

        # Open camera in thread pool (blocking operation)
        loop = asyncio.get_event_loop()
        self._cap = await loop.run_in_executor(
            self._executor,
            self._open_camera
        )

        if self._cap is None or not self._cap.isOpened():
            print(f"[VideoFeed] Failed to open camera device {self.device}")
            self._running = False
            return

        # Load face cascade if needed
        if self.enable_face_detection:
            try:
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self._face_cascade = cv2.CascadeClassifier(cascade_path)
                print("[VideoFeed] Face detection enabled")
            except Exception as e:
                print(f"[VideoFeed] Face detection unavailable: {e}")
                self._face_cascade = None

        self._task = asyncio.create_task(self._capture_loop())
        print(f"[VideoFeed] Started - device {self.device} at {self.width}x{self.height}")

    def _open_camera(self) -> cv2.VideoCapture | None:
        """Open camera (runs in thread pool)."""
        cap = cv2.VideoCapture(self.device)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.fps)
            return cap
        return None

    async def _capture_loop(self) -> None:
        """Main capture loop."""
        frame_time = 1.0 / self.fps
        loop = asyncio.get_event_loop()

        try:
            while self._running and self._cap and self._cap.isOpened():
                start = time.perf_counter()

                # Read frame in thread pool (blocking operation)
                ret, frame = await loop.run_in_executor(
                    self._executor,
                    self._read_frame
                )

                if ret and frame is not None:
                    # Analyze frame
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
            print(f"[VideoFeed] Capture error: {e}")

    def _read_frame(self) -> tuple[bool, np.ndarray | None]:
        """Read frame from camera (runs in thread pool)."""
        if self._cap:
            return self._cap.read()
        return False, None

    def _analyze(self, frame: np.ndarray) -> None:
        """Analyze frame for motion, light level, and optional features.

        Args:
            frame: BGR frame from OpenCV
        """
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

        # Face detection (expensive, run less frequently)
        if self._face_cascade is not None:
            # Only run every 5th frame to reduce CPU load
            if not hasattr(self, '_face_frame_count'):
                self._face_frame_count = 0
            self._face_frame_count += 1

            if self._face_frame_count >= 5:
                self._face_frame_count = 0
                faces = self._face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(30, 30)
                )
                self.faces = [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

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

        if self._cap:
            self._cap.release()
            self._cap = None

        self._executor.shutdown(wait=False)
        print("[VideoFeed] Stopped")

    @property
    def is_running(self) -> bool:
        """Check if video feed is running."""
        return self._running and self._cap is not None and self._cap.isOpened()


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
