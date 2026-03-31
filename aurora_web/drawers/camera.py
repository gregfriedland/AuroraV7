"""Camera drawer - converts video feed to LED matrix palette indices."""

import numpy as np
from aurora_web.drawers.base import Drawer, DrawerContext


class CameraDrawer(Drawer):
    """Displays camera feed mapped to the color palette.

    Converts camera frames to grayscale luminance, then maps
    brightness values to palette indices. Supports edge-detection
    and motion-map display modes.
    """

    # Display modes
    MODE_LUMINANCE = 1
    MODE_EDGES = 2
    MODE_MOTION = 3

    def __init__(self, width: int, height: int, palette_size: int = 4096,
                 video_feed=None):
        """Initialize camera drawer.

        Args:
            width: Matrix width in pixels
            height: Matrix height in pixels
            palette_size: Number of colors in palette
            video_feed: VideoFeed or MockVideoFeed instance
        """
        super().__init__("Camera", width, height, palette_size)
        self.video_feed = video_feed

        # Settings
        self.settings = {
            "mode": self.MODE_LUMINANCE,
            "brightness": 50,
            "contrast": 50,
            "mirror": 1,
            "colorSpeed": 0,
            "zoom": 2,       # 1-8x digital zoom
            "zoomX": 42,     # 0=left, 50=center, 100=right
            "zoomY": 100,    # 0=top, 50=center, 100=bottom
            "faceZoom": 1,   # 0=off, 1=on (2x2 montage of detected faces)
        }
        self.settings_ranges = {
            "mode": (1, 3),
            "brightness": (0, 100),
            "contrast": (0, 100),
            "mirror": (0, 1),
            "colorSpeed": (0, 50),
            "zoom": (1, 8),
            "zoomX": (0, 100),
            "zoomY": (0, 100),
            "faceZoom": (0, 1),
        }
        self.color_index = 0

        self.reset()

    def reset(self) -> None:
        """Reset drawer state."""
        self._prev_frame = None
        self._smoothed_faces: list[tuple[float, float, float, float]] = []
        self._face_targets: list[tuple[int, int, int, int]] = []
        self._face_target_time: float = 0.0
        self._last_face_seen: float = 0.0  # monotonic time of last detection
        self._palette_scale: float = 2.0  # auto-scale factor for palette mapping
        self._palette_scale_time: float = 0.0

    def randomize_settings(self) -> None:
        """Randomize settings but keep faceZoom on and colorSpeed slow."""
        super().randomize_settings()
        self.settings["faceZoom"] = 1
        self.settings["colorSpeed"] = 0

    def set_video_feed(self, video_feed) -> None:
        """Set or replace the video feed source."""
        self.video_feed = video_feed

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        """Draw camera frame mapped to palette indices.

        Returns:
            Array of palette indices, shape (height, width)
        """
        if self.video_feed is None:
            return self._fallback_pattern(ctx)

        video_input = self.video_feed.get_input()

        if video_input.frame is None:
            return self._fallback_pattern(ctx)

        # Face zoom montage mode
        use_face_zoom = self.settings["faceZoom"] and (
            video_input.faces or self._smoothed_faces
        )
        if use_face_zoom:
            # Use detected faces, or keep last known positions if face lost
            faces = video_input.faces if video_input.faces else None
            smoothed = self._smooth_faces(faces)
            normalized = self._build_face_montage(video_input.frame, smoothed)
        else:
            frame = self._apply_zoom(video_input.frame)
            mode = self.settings["mode"]

            if mode == self.MODE_EDGES:
                normalized = self._compute_edges(frame)
            elif mode == self.MODE_MOTION and video_input.motion_map is not None:
                normalized = self._resize(self._apply_zoom_2d(video_input.motion_map))
            else:
                normalized = self._frame_to_luminance(frame)

        # Apply brightness/contrast
        normalized = self._adjust_brightness_contrast(normalized)

        # Mirror horizontally (selfie-style) if enabled
        if self.settings["mirror"]:
            normalized = np.fliplr(normalized)

        # Auto-scale: recalculate every 15s so max luminance maps to full palette
        import time
        now = time.monotonic()
        if now - self._palette_scale_time >= 15.0:
            self._palette_scale_time = now
            max_val = normalized.max()
            if max_val > 0.05:
                self._palette_scale = 1.0 / max_val
            else:
                self._palette_scale = 1.0

        # Map to palette indices (auto-scale stretches range to fill palette)
        scaled = np.clip(normalized * self._palette_scale, 0.0, 1.0)
        indices = (scaled * (self.palette_size - 1)).astype(np.int32)

        # Apply color cycling
        indices = (indices + int(self.color_index)) % self.palette_size
        self.color_index = (self.color_index + self.settings["colorSpeed"] * 0.1) % self.palette_size

        return indices

    def _smooth_faces(self, faces: list[tuple[int, int, int, int]] | None,
                      alpha: float = 0.03,
                      retarget_interval: float = 15.0,
                      hold_time: float = 3.0,
                      ) -> list[tuple[int, int, int, int]]:
        """Exponential moving average on face rectangles for smooth panning.

        Only accepts new face targets every retarget_interval seconds,
        then slowly lerps toward them. When faces are lost, holds the
        last position for hold_time seconds before accepting new faces
        (debounce to prevent flickering).

        Args:
            faces: Detected face rects, or None to hold current position
            alpha: Blend factor per frame (0.03 at 40fps ≈ 1s to settle)
            retarget_interval: Seconds between accepting new target positions
            hold_time: Seconds to hold position after face loss before
                       accepting new detections (debounce)

        Returns:
            Smoothed face rects as integer tuples
        """
        import time
        now = time.monotonic()

        if faces:
            self._last_face_seen = now

        # Hold current position if no faces or within debounce window after loss
        in_hold = (
            self._smoothed_faces
            and (not faces or now - self._last_face_seen > hold_time)
            and not faces
        )
        if in_hold or (faces is None and self._smoothed_faces):
            # Just lerp toward existing targets (keeps animation smooth)
            if self._face_targets and self._smoothed_faces:
                blended = []
                for (sx, sy, sw, sh), (tx, ty, tw, th) in zip(
                    self._smoothed_faces, self._face_targets
                ):
                    blended.append((
                        sx + alpha * (tx - sx),
                        sy + alpha * (ty - sy),
                        sw + alpha * (tw - sw),
                        sh + alpha * (th - sh),
                    ))
                self._smoothed_faces = blended
            return [(int(round(x)), int(round(y)), int(round(w)), int(round(h)))
                    for x, y, w, h in self._smoothed_faces]

        detected = faces[:4] if faces else []
        if not detected:
            return [(int(round(x)), int(round(y)), int(round(w)), int(round(h)))
                    for x, y, w, h in self._smoothed_faces]

        # First detection ever — snap immediately
        if not self._face_targets:
            self._face_targets = detected
            self._face_target_time = now
            self._smoothed_faces = [(float(x), float(y), float(w), float(h))
                                    for x, y, w, h in detected]
        elif now - self._face_target_time >= retarget_interval:
            # Time for a new target — use the first N faces matching current count
            # to avoid layout jumps; if count differs, still retarget smoothly
            self._face_targets = detected
            self._face_target_time = now
            # If face count changed, re-init smoothed to match
            if len(detected) != len(self._smoothed_faces):
                self._smoothed_faces = [(float(x), float(y), float(w), float(h))
                                        for x, y, w, h in detected]

        # Lerp toward current targets
        if len(self._smoothed_faces) == len(self._face_targets):
            blended = []
            for (sx, sy, sw, sh), (tx, ty, tw, th) in zip(
                self._smoothed_faces, self._face_targets
            ):
                blended.append((
                    sx + alpha * (tx - sx),
                    sy + alpha * (ty - sy),
                    sw + alpha * (tw - sw),
                    sh + alpha * (th - sh),
                ))
            self._smoothed_faces = blended

        return [(int(round(x)), int(round(y)), int(round(w)), int(round(h)))
                for x, y, w, h in self._smoothed_faces]

    def _crop_face(self, frame: np.ndarray, face: tuple[int, int, int, int],
                   target_aspect: float, margin: float = 0.5) -> np.ndarray:
        """Crop a face region matching the target aspect ratio.

        Expands the crop around the face center to match target_aspect
        (width/height), preserving aspect ratio with no distortion.

        Args:
            frame: RGB source frame (h, w, 3)
            face: (x, y, w, h) face rectangle in source pixel coords
            target_aspect: Desired width/height ratio of the crop
            margin: Fraction of face size to add as padding (0.5 = 50%)

        Returns:
            Cropped RGB region matching target aspect ratio
        """
        fh, fw = frame.shape[:2]
        fx, fy, face_w, face_h = face

        # Start with padded region around face
        crop_w = face_w * (1 + 2 * margin)
        crop_h = face_h * (1 + 2 * margin)

        # Expand to match target aspect ratio
        crop_aspect = crop_w / max(crop_h, 1)
        if crop_aspect < target_aspect:
            # Too tall — widen
            crop_w = crop_h * target_aspect
        else:
            # Too wide — heighten
            crop_h = crop_w / target_aspect

        # Center on face
        cx = fx + face_w / 2
        cy = fy + face_h / 2

        x0 = int(max(0, cx - crop_w / 2))
        y0 = int(max(0, cy - crop_h / 2))
        x1 = int(min(fw, x0 + crop_w))
        y1 = int(min(fh, y0 + crop_h))

        # Re-adjust if clamped to edge
        x0 = max(0, x1 - int(crop_w))
        y0 = max(0, y1 - int(crop_h))

        return frame[y0:y1, x0:x1]

    def _resize_rgb_to(self, frame: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
        """Resize an RGB frame to arbitrary target dimensions using nearest-neighbor.

        Args:
            frame: RGB frame (h, w, 3)
            target_h: Target height
            target_w: Target width

        Returns:
            Resized frame (target_h, target_w, 3)
        """
        src_h, src_w = frame.shape[:2]
        row_idx = (np.arange(target_h) * src_h // target_h).astype(int)
        col_idx = (np.arange(target_w) * src_w // target_w).astype(int)
        return frame[np.ix_(row_idx, col_idx)]

    def _build_face_montage(self, frame: np.ndarray,
                            faces: list[tuple[int, int, int, int]]) -> np.ndarray:
        """Build a face montage and return normalized luminance at matrix size.

        Layout adapts to face count:
          1 face  -> full matrix
          2 faces -> left/right split (each 16x18)
          3 faces -> top-left, top-right, bottom-center
          4 faces -> 2x2 grid (each 16x9)

        Args:
            frame: RGB source frame from camera
            faces: List of (x, y, w, h) face rectangles

        Returns:
            Normalized float array (0.0-1.0), shape (height, width)
        """
        faces = faces[:4]  # Limit to 4 faces
        n = len(faces)

        # Assemble an RGB montage at matrix resolution, then convert to luminance
        montage = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        if n == 1:
            # Single face fills the whole matrix
            aspect = self.width / max(self.height, 1)
            crop = self._crop_face(frame, faces[0], aspect)
            montage[:, :] = self._resize_rgb_to(crop, self.height, self.width)

        elif n == 2:
            # Left/right split — each half is width//2 wide
            half_w = self.width // 2
            aspect = half_w / max(self.height, 1)
            for i, face in enumerate(faces):
                crop = self._crop_face(frame, face, aspect)
                resized = self._resize_rgb_to(crop, self.height, half_w)
                montage[:, i * half_w:(i + 1) * half_w] = resized

        elif n == 3:
            # Top row: 2 faces side-by-side; bottom row: 1 face centered
            half_w = self.width // 2
            half_h = self.height // 2
            top_aspect = half_w / max(half_h, 1)
            bot_h = self.height - half_h
            center_w = self.width - 2 * (self.width // 4)
            bot_aspect = center_w / max(bot_h, 1)

            crop0 = self._crop_face(frame, faces[0], top_aspect)
            montage[:half_h, :half_w] = self._resize_rgb_to(crop0, half_h, half_w)

            crop1 = self._crop_face(frame, faces[1], top_aspect)
            montage[:half_h, half_w:] = self._resize_rgb_to(crop1, half_h, self.width - half_w)

            quarter_w = self.width // 4
            crop2 = self._crop_face(frame, faces[2], bot_aspect)
            montage[half_h:, quarter_w:quarter_w + center_w] = self._resize_rgb_to(
                crop2, bot_h, center_w
            )

        else:
            # 4 faces: 2x2 grid
            half_w = self.width // 2
            half_h = self.height // 2
            positions = [(0, 0), (0, half_w), (half_h, 0), (half_h, half_w)]
            for i, face in enumerate(faces[:4]):
                y_off, x_off = positions[i]
                tile_h = half_h if i < 2 else self.height - half_h
                tile_w = half_w if i % 2 == 0 else self.width - half_w
                aspect = tile_w / max(tile_h, 1)
                crop = self._crop_face(frame, face, aspect)
                montage[y_off:y_off + tile_h, x_off:x_off + tile_w] = self._resize_rgb_to(
                    crop, tile_h, tile_w
                )

        # Convert assembled montage to luminance (BT.709)
        luminance = (0.2126 * montage[:, :, 0] +
                     0.7152 * montage[:, :, 1] +
                     0.0722 * montage[:, :, 2])
        return luminance / 255.0

    def _zoom_crop(self, h: int, w: int) -> tuple[int, int, int, int]:
        """Compute crop region for current zoom settings.

        Returns:
            (y_start, y_end, x_start, x_end)
        """
        zoom = max(1, self.settings["zoom"])
        crop_w = w // zoom
        crop_h = h // zoom

        # zoomX/zoomY are 0-100 percentages for the crop center
        cx = int(self.settings["zoomX"] / 100.0 * w)
        cy = int(self.settings["zoomY"] / 100.0 * h)

        x0 = max(0, min(cx - crop_w // 2, w - crop_w))
        y0 = max(0, min(cy - crop_h // 2, h - crop_h))
        return y0, y0 + crop_h, x0, x0 + crop_w

    def _apply_zoom(self, frame: np.ndarray) -> np.ndarray:
        """Crop an RGB frame according to zoom settings."""
        if self.settings["zoom"] <= 1:
            return frame
        y0, y1, x0, x1 = self._zoom_crop(frame.shape[0], frame.shape[1])
        return frame[y0:y1, x0:x1]

    def _apply_zoom_2d(self, arr: np.ndarray) -> np.ndarray:
        """Crop a 2D array according to zoom settings."""
        if self.settings["zoom"] <= 1:
            return arr
        y0, y1, x0, x1 = self._zoom_crop(arr.shape[0], arr.shape[1])
        return arr[y0:y1, x0:x1]

    def _frame_to_luminance(self, frame: np.ndarray) -> np.ndarray:
        """Convert RGB frame to luminance and resize to matrix dimensions.

        Returns:
            Normalized float array (0.0-1.0), shape (height, width)
        """
        # Resize first, then convert (more efficient for small targets)
        resized = self._resize_rgb(frame)
        # ITU-R BT.709 luminance
        luminance = (0.2126 * resized[:, :, 0] +
                     0.7152 * resized[:, :, 1] +
                     0.0722 * resized[:, :, 2])
        return luminance / 255.0

    def _compute_edges(self, frame: np.ndarray) -> np.ndarray:
        """Compute edge-detection on frame using Sobel-like kernels.

        Returns:
            Normalized float array (0.0-1.0), shape (height, width)
        """
        luminance = self._frame_to_luminance(frame)

        # Simple Sobel edge detection without OpenCV dependency
        # Horizontal kernel
        gx = np.zeros_like(luminance)
        gx[:, 1:-1] = luminance[:, 2:] - luminance[:, :-2]
        # Vertical kernel
        gy = np.zeros_like(luminance)
        gy[1:-1, :] = luminance[2:, :] - luminance[:-2, :]

        edges = np.sqrt(gx**2 + gy**2)
        # Normalize to 0-1
        max_val = edges.max()
        if max_val > 0:
            edges = edges / max_val
        return edges

    def _resize(self, arr: np.ndarray) -> np.ndarray:
        """Resize a 2D float array to matrix dimensions using nearest-neighbor.

        Args:
            arr: Input 2D array

        Returns:
            Resized array, shape (self.height, self.width)
        """
        src_h, src_w = arr.shape[:2]
        row_idx = (np.arange(self.height) * src_h // self.height).astype(int)
        col_idx = (np.arange(self.width) * src_w // self.width).astype(int)
        return arr[np.ix_(row_idx, col_idx)]

    def _resize_rgb(self, frame: np.ndarray) -> np.ndarray:
        """Resize an RGB frame to matrix dimensions using nearest-neighbor.

        Args:
            frame: RGB frame (h, w, 3)

        Returns:
            Resized frame, shape (self.height, self.width, 3)
        """
        src_h, src_w = frame.shape[:2]
        row_idx = (np.arange(self.height) * src_h // self.height).astype(int)
        col_idx = (np.arange(self.width) * src_w // self.width).astype(int)
        return frame[np.ix_(row_idx, col_idx)]

    def _adjust_brightness_contrast(self, arr: np.ndarray) -> np.ndarray:
        """Apply brightness and contrast adjustment.

        Args:
            arr: Normalized float array (0.0-1.0)

        Returns:
            Adjusted array, clipped to 0.0-1.0
        """
        # brightness: 0=dark, 50=neutral, 100=bright
        brightness_offset = (self.settings["brightness"] - 50) / 100.0

        # contrast: 0=flat, 50=neutral, 100=high
        contrast_factor = self.settings["contrast"] / 50.0

        result = (arr - 0.5) * contrast_factor + 0.5 + brightness_offset
        return np.clip(result, 0.0, 1.0)

    def _fallback_pattern(self, ctx: DrawerContext) -> np.ndarray:
        """Generate a fallback pattern when no video feed is available.

        Shows a slow pulsing gradient to indicate "waiting for camera".
        """
        x = np.arange(self.width)
        pulse = (np.sin(ctx.time * 2.0) + 1.0) / 2.0
        indices = ((x / max(self.width - 1, 1)) * pulse * (self.palette_size - 1)).astype(np.int32)
        return np.tile(indices, (self.height, 1))
