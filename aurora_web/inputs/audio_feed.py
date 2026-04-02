"""Audio feed for beat detection and spectrum analysis."""

import numpy as np
import asyncio
import os
import stat
import time
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class AudioInput:
    """Audio analysis data passed to drawers."""
    is_active: bool = False                # True when audio stream is connected
    bpm: float | None = None           # Current tempo estimate (60-200)
    beat_onset: bool = False              # True on beat hit
    beat_phase: float = 0.0               # 0.0-1.0 position within beat
    beat_index: int = 0                    # Which beat in bar (0-3)
    bar_phase: float = 0.0                # 0.0-1.0 position within full bar
    spectrum: np.ndarray | None = None # FFT bins (16 bands)
    volume: float = 0.0                   # 0.0-1.0 current volume level
    bass: float = 0.0                     # 0.0-1.0 low frequency energy
    mids: float = 0.0                     # 0.0-1.0 mid frequency energy
    highs: float = 0.0                    # 0.0-1.0 high frequency energy


class BeatTracker:
    """Spectral flux onset detection + autocorrelation tempo + phase-locked oscillator.

    Three-stage pipeline:
    1. Spectral flux: half-wave rectified difference of consecutive FFT frames
    2. Autocorrelation: finds dominant periodicity in onset strength buffer (60-200 BPM)
    3. Phase-locked oscillator: phase 0→4 (one 4/4 bar), nudged toward detected onsets
    """

    def __init__(self, analysis_fps: float = 21.5):
        self.analysis_fps = analysis_fps

        # Spectral flux state
        self._prev_fft: np.ndarray | None = None
        self._flux_mean: float = 0.0
        self._flux_var: float = 0.0
        self._flux_ema_alpha: float = 0.02  # ~50 frame time constant

        # Onset strength circular buffer (~4 seconds)
        self._onset_buf_size = int(analysis_fps * 4)
        self._onset_buf = np.zeros(self._onset_buf_size, dtype=np.float32)
        self._onset_idx = 0

        # Tempo estimation
        self._bpm: float = 120.0
        self._tempo_confidence: float = 0.0
        self._last_tempo_time: float = 0.0
        self._tempo_update_interval: float = 2.0  # seconds

        # Phase-locked oscillator (0→4 = one full bar)
        self._phase: float = 0.0
        self._phase_correction: float = 0.1

        # Outputs
        self.bpm: float = 120.0
        self.beat_onset: bool = False
        self.beat_phase: float = 0.0
        self.beat_index: int = 0
        self.bar_phase: float = 0.0

    def reset(self) -> None:
        self._prev_fft = None
        self._flux_mean = 0.0
        self._flux_var = 0.0
        self._onset_buf[:] = 0
        self._onset_idx = 0
        self._bpm = 120.0
        self._tempo_confidence = 0.0
        self._last_tempo_time = 0.0
        self._phase = 0.0
        self.bpm = 120.0
        self.beat_onset = False
        self.beat_phase = 0.0
        self.beat_index = 0
        self.bar_phase = 0.0

    def update(self, fft_magnitudes: np.ndarray, dt: float) -> None:
        """Process one frame of FFT magnitudes.

        Args:
            fft_magnitudes: Raw FFT magnitude bins (e.g. 1025 bins from rfft of 2048 samples)
            dt: Time since last frame in seconds
        """
        now = time.time()

        # --- Stage 1: Spectral flux onset detection ---
        is_onset = False
        if self._prev_fft is not None and len(fft_magnitudes) == len(self._prev_fft):
            # Half-wave rectified spectral flux
            diff = fft_magnitudes - self._prev_fft
            flux = float(np.sum(np.maximum(diff, 0.0)))

            # Update running mean/variance with EMA
            a = self._flux_ema_alpha
            self._flux_mean += a * (flux - self._flux_mean)
            deviation = (flux - self._flux_mean) ** 2
            self._flux_var += a * (deviation - self._flux_var)
            stddev = max(np.sqrt(self._flux_var), 1e-6)

            # Onset = flux exceeds mean + 1.5 * stddev
            threshold = self._flux_mean + 1.5 * stddev
            onset_strength = max(0.0, (flux - threshold) / stddev)
            is_onset = flux > threshold

            # Store in circular buffer
            self._onset_buf[self._onset_idx % self._onset_buf_size] = onset_strength
            self._onset_idx += 1
        else:
            self._onset_buf[self._onset_idx % self._onset_buf_size] = 0.0
            self._onset_idx += 1

        self._prev_fft = fft_magnitudes.copy()

        # --- Stage 2: Autocorrelation tempo estimation (every ~2 seconds) ---
        if now - self._last_tempo_time > self._tempo_update_interval and self._onset_idx >= self._onset_buf_size:
            self._estimate_tempo()
            self._last_tempo_time = now

        # --- Stage 3: Phase-locked oscillator ---
        old_phase = self._phase

        # Advance phase: dt * (bpm / 60) gives beats per dt; phase runs 0→4
        beats_per_second = self._bpm / 60.0
        self._phase += dt * beats_per_second
        self._phase %= 4.0

        # Nudge phase toward nearest integer beat on onset
        if is_onset:
            nearest_beat = round(self._phase)
            if nearest_beat >= 4:
                nearest_beat = 0
            # Phase error: signed distance to nearest beat
            error = nearest_beat - self._phase
            # Wrap to [-2, 2]
            if error > 2.0:
                error -= 4.0
            elif error < -2.0:
                error += 4.0
            self._phase += self._phase_correction * error
            self._phase %= 4.0

        # Detect beat onset: phase crossed an integer boundary
        self.beat_onset = False
        if old_phase > self._phase:
            # Phase wrapped around 4→0
            self.beat_onset = True
        else:
            # Check if we crossed any integer
            old_beat = int(old_phase)
            new_beat = int(self._phase)
            if new_beat != old_beat and self._phase != old_phase:
                self.beat_onset = True

        # Set outputs
        self.bpm = self._bpm
        self.beat_phase = self._phase % 1.0
        self.beat_index = int(self._phase) % 4
        self.bar_phase = self._phase / 4.0

    def _estimate_tempo(self) -> None:
        """Autocorrelation-based tempo estimation from onset strength buffer."""
        buf = self._onset_buf.copy()

        # Remove DC
        buf -= np.mean(buf)

        # Autocorrelation via FFT (O(n log n))
        n = len(buf)
        fft = np.fft.rfft(buf, n=2 * n)
        acf = np.fft.irfft(fft * np.conj(fft))[:n]

        # Normalize
        if acf[0] > 0:
            acf /= acf[0]

        # Convert BPM range to lag range
        # lag = analysis_fps * 60 / bpm
        min_lag = int(self.analysis_fps * 60.0 / 200.0)  # 200 BPM
        max_lag = int(self.analysis_fps * 60.0 / 60.0)   # 60 BPM
        min_lag = max(1, min_lag)
        max_lag = min(max_lag, n - 1)

        if min_lag >= max_lag:
            return

        # Find peak in valid lag range
        search = acf[min_lag:max_lag + 1]
        peak_idx = np.argmax(search)
        peak_lag = peak_idx + min_lag
        peak_val = search[peak_idx]

        if peak_lag > 0 and peak_val > 0.1:
            estimated_bpm = self.analysis_fps * 60.0 / peak_lag
            estimated_bpm = float(np.clip(estimated_bpm, 60.0, 200.0))

            # Smoothly nudge toward estimate (weighted by confidence)
            confidence = min(peak_val, 1.0)
            blend = 0.3 * confidence
            self._bpm += blend * (estimated_bpm - self._bpm)
            self._bpm = float(np.clip(self._bpm, 60.0, 200.0))
            self._tempo_confidence = confidence


class AudioFeed:
    """Captures and analyzes audio for beat detection and spectrum.

    Uses external audio capture (parec for PulseAudio, arecord for ALSA)
    and performs real-time FFT analysis for beat detection.
    """

    def __init__(
        self,
        source: str = "pulse",
        sample_rate: int = 44100,
        channels: int = 1,
        buffer_size: int = 2048,
        num_bands: int = 16,
        onset_threshold: float = 0.6,
        min_beat_interval: float = 0.2,
    ):
        """Initialize audio feed.

        Args:
            source: Audio source - "pulse", "alsa:hw:0", "file:/path",
                    or "pipe:/path" (raw S16LE FIFO from shairport-sync)
            sample_rate: Audio sample rate
            channels: Number of input channels (1=mono, 2=stereo; stereo is downmixed)
            buffer_size: FFT buffer size
            num_bands: Number of spectrum bands
            onset_threshold: Threshold for beat detection (0-1)
            min_beat_interval: Minimum seconds between beats
        """
        self.source = source
        self.sample_rate = sample_rate
        self.channels = channels
        self.buffer_size = buffer_size
        self.num_bands = num_bands
        self.onset_threshold = onset_threshold
        self.min_beat_interval = min_beat_interval

        # State
        self.bpm: float | None = None
        self.beat_onset: bool = False
        self.beat_phase: float = 0.0
        self.beat_index: int = 0
        self.bar_phase: float = 0.0
        self.spectrum: np.ndarray | None = None
        self.volume: float = 0.0

        # Beat tracker
        analysis_fps = sample_rate / buffer_size  # ~21.5 Hz
        self._beat_tracker = BeatTracker(analysis_fps=analysis_fps)
        self._last_analyze_time: float = 0.0

        # Process
        self._process: asyncio.subprocess.Process | None = None
        self._running: bool = False
        self._task: asyncio.Task | None = None
        self.is_active: bool = False  # True when audio is flowing

    def _reset_state(self) -> None:
        """Reset audio analysis state (on disconnect)."""
        self.bpm = None
        self.beat_onset = False
        self.beat_phase = 0.0
        self.beat_index = 0
        self.bar_phase = 0.0
        self.spectrum = None
        self.volume = 0.0
        self._beat_tracker.reset()
        self._last_analyze_time = 0.0

    def _build_capture_command(self) -> list[str]:
        """Build the audio capture command based on source."""
        if self.source == "pulse":
            # PulseAudio capture
            return [
                "parec",
                "--format=s16le",
                f"--rate={self.sample_rate}",
                "--channels=1",
            ]
        elif self.source.startswith("alsa:"):
            # ALSA capture
            device = self.source[5:]  # Remove "alsa:" prefix
            return [
                "arecord",
                "-D", device,
                "-f", "S16_LE",
                "-r", str(self.sample_rate),
                "-c", "1",
                "-t", "raw",
            ]
        elif self.source.startswith("pipe:"):
            # Named pipe (FIFO) — raw S16LE PCM (e.g. from shairport-sync)
            pipe_path = self.source[5:]
            return ["cat", pipe_path]
        elif self.source.startswith("file:"):
            # File playback via ffmpeg
            filepath = self.source[5:]
            return [
                "ffmpeg",
                "-i", filepath,
                "-f", "s16le",
                "-ar", str(self.sample_rate),
                "-ac", "1",
                "-",
            ]
        else:
            raise ValueError(f"Unknown audio source: {self.source}")

    async def start(self) -> None:
        """Start audio capture and analysis."""
        if self._running:
            return

        self._running = True

        # Create FIFO for pipe source if it doesn't exist
        if self.source.startswith("pipe:"):
            pipe_path = self.source[5:]
            if not os.path.exists(pipe_path):
                try:
                    os.mkfifo(pipe_path)
                    print(f"[AudioFeed] Created FIFO: {pipe_path}")
                except OSError as e:
                    print(f"[AudioFeed] Failed to create FIFO {pipe_path}: {e}")
            elif not stat.S_ISFIFO(os.stat(pipe_path).st_mode):
                print(f"[AudioFeed] WARNING: {pipe_path} exists but is not a FIFO")

        cmd = self._build_capture_command()

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            self._task = asyncio.create_task(self._read_loop())
            print(f"[AudioFeed] Started with source: {self.source}")
        except FileNotFoundError as e:
            print(f"[AudioFeed] Failed to start - command not found: {cmd[0]}")
            self._running = False
        except Exception as e:
            print(f"[AudioFeed] Failed to start: {e}")
            self._running = False

    async def _read_loop(self) -> None:
        """Read audio data and analyze.

        For pipe sources, auto-reconnects when the writer disconnects
        (e.g. AirPlay stream ends) and waits for the next connection.
        """
        bytes_per_sample = 2  # 16-bit audio
        bytes_needed = self.buffer_size * bytes_per_sample * self.channels
        is_pipe = self.source.startswith("pipe:")

        try:
            while self._running:
                if self._process is None or self._process.returncode is not None:
                    if not is_pipe:
                        break  # Non-pipe sources don't reconnect

                    # Reset state on disconnect
                    self._reset_state()
                    self.is_active = False
                    print("[AudioFeed] Waiting for AirPlay connection...")

                    # Restart cat on the FIFO (blocks until writer connects)
                    cmd = self._build_capture_command()
                    self._process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )

                data = await self._process.stdout.read(bytes_needed)
                if not data:
                    if is_pipe:
                        # EOF — writer disconnected, loop will reconnect
                        print("[AudioFeed] AirPlay disconnected")
                        self._process = None
                        continue
                    await asyncio.sleep(0.01)
                    continue

                # Mark active on first data received
                if not self.is_active:
                    self.is_active = True
                    print("[AudioFeed] AirPlay connected")

                # Convert bytes to samples
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

                # Downmix stereo to mono
                if self.channels == 2 and len(samples) >= 2:
                    samples = (samples[0::2] + samples[1::2]) / 2.0

                if len(samples) >= self.buffer_size // 2:
                    self._analyze(samples)

                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.005)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[AudioFeed] Read error: {e}")

    def _analyze(self, samples: np.ndarray) -> None:
        """Compute spectrum and detect beats.

        Args:
            samples: Audio samples as float array (-1 to 1)
        """
        now = time.time()
        dt = now - self._last_analyze_time if self._last_analyze_time > 0 else 1.0 / self._beat_tracker.analysis_fps
        self._last_analyze_time = now

        # Compute FFT
        window = np.hanning(len(samples))
        fft = np.abs(np.fft.rfft(samples * window))

        # Volume (RMS)
        self.volume = float(np.sqrt(np.mean(samples ** 2)))

        # Pass full FFT to beat tracker
        self._beat_tracker.update(fft, dt)
        self.bpm = self._beat_tracker.bpm
        self.beat_onset = self._beat_tracker.beat_onset
        self.beat_phase = self._beat_tracker.beat_phase
        self.beat_index = self._beat_tracker.beat_index
        self.bar_phase = self._beat_tracker.bar_phase

        # Create spectrum bands (logarithmic spacing)
        freq_bins = len(fft)
        if freq_bins < self.num_bands:
            self.spectrum = fft[:self.num_bands] if len(fft) >= self.num_bands else np.zeros(self.num_bands)
        else:
            # Logarithmic band edges
            band_edges = np.logspace(0, np.log10(freq_bins), self.num_bands + 1).astype(int)
            band_edges = np.clip(band_edges, 0, freq_bins)

            self.spectrum = np.array([
                np.mean(fft[band_edges[i]:band_edges[i+1]]) if band_edges[i+1] > band_edges[i] else 0
                for i in range(self.num_bands)
            ], dtype=np.float32)

        # Normalize spectrum for display
        max_val = np.max(self.spectrum)
        if max_val > 0:
            self.spectrum = self.spectrum / max_val

    def get_input(self) -> AudioInput:
        """Get current audio input state for drawers.

        Returns:
            AudioInput dataclass with current audio state
        """
        spectrum = self.spectrum

        # Calculate bass/mids/highs from spectrum
        if spectrum is not None and len(spectrum) >= self.num_bands:
            bass = float(np.mean(spectrum[:3]))
            mids = float(np.mean(spectrum[3:10]))
            highs = float(np.mean(spectrum[10:]))
        else:
            bass = mids = highs = 0.0

        return AudioInput(
            is_active=self.is_active,
            bpm=self.bpm,
            beat_onset=self.beat_onset,
            beat_phase=self.beat_phase,
            beat_index=self.beat_index,
            bar_phase=self.bar_phase,
            spectrum=spectrum.copy() if spectrum is not None else None,
            volume=self.volume,
            bass=bass,
            mids=mids,
            highs=highs,
        )

    async def stop(self) -> None:
        """Stop audio capture."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self._process.kill()

        print("[AudioFeed] Stopped")

    @property
    def is_running(self) -> bool:
        """Check if audio feed is running."""
        return self._running and self._process is not None


class MockAudioFeed:
    """Mock audio feed for testing without actual audio input.

    Generates synthetic beats at a configurable BPM.
    """

    def __init__(self, bpm: float = 120.0):
        """Initialize mock audio feed.

        Args:
            bpm: Beats per minute to simulate
        """
        self.bpm = bpm
        self._start_time = 0.0
        self._running = False

    async def start(self) -> None:
        """Start mock audio feed."""
        self._running = True
        self._start_time = time.time()
        print(f"[MockAudioFeed] Started at {self.bpm} BPM")

    async def stop(self) -> None:
        """Stop mock audio feed."""
        self._running = False
        print("[MockAudioFeed] Stopped")

    def get_input(self) -> AudioInput:
        """Get simulated audio input."""
        if not self._running:
            return AudioInput()

        now = time.time()
        elapsed = now - self._start_time
        beats_per_second = self.bpm / 60.0

        # Phase within a 4-beat bar (0→4)
        bar_phase_raw = (elapsed * beats_per_second) % 4.0
        beat_index = int(bar_phase_raw) % 4
        beat_phase = bar_phase_raw % 1.0
        bar_phase = bar_phase_raw / 4.0

        # Detect beat onset (phase near zero)
        beat_onset = beat_phase < 0.05

        # Generate fake spectrum (pulsing with beat)
        intensity = 1.0 - beat_phase  # Decay after beat
        spectrum = np.random.rand(16).astype(np.float32) * 0.3 + intensity * 0.7
        spectrum[:3] *= 1.5 if beat_onset else 1.0  # Boost bass on beat

        return AudioInput(
            bpm=self.bpm,
            beat_onset=beat_onset,
            beat_phase=beat_phase,
            beat_index=beat_index,
            bar_phase=bar_phase,
            spectrum=spectrum,
            volume=0.5 + intensity * 0.3,
            bass=float(np.mean(spectrum[:3])),
            mids=float(np.mean(spectrum[3:10])),
            highs=float(np.mean(spectrum[10:])),
        )

    @property
    def is_running(self) -> bool:
        return self._running
