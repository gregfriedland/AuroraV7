"""Audio feed for beat detection and spectrum analysis."""

import numpy as np
import asyncio
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional, List
import struct


@dataclass
class AudioInput:
    """Audio analysis data passed to drawers."""
    bpm: Optional[float] = None           # Current tempo estimate (60-200)
    beat_onset: bool = False              # True on beat hit
    beat_phase: float = 0.0               # 0.0-1.0 position within beat
    spectrum: Optional[np.ndarray] = None # FFT bins (16 bands)
    volume: float = 0.0                   # 0.0-1.0 current volume level
    bass: float = 0.0                     # 0.0-1.0 low frequency energy
    mids: float = 0.0                     # 0.0-1.0 mid frequency energy
    highs: float = 0.0                    # 0.0-1.0 high frequency energy


class AudioFeed:
    """Captures and analyzes audio for beat detection and spectrum.

    Uses external audio capture (parec for PulseAudio, arecord for ALSA)
    and performs real-time FFT analysis for beat detection.
    """

    def __init__(
        self,
        source: str = "pulse",
        sample_rate: int = 44100,
        buffer_size: int = 2048,
        num_bands: int = 16,
        onset_threshold: float = 0.6,
        min_beat_interval: float = 0.2,
    ):
        """Initialize audio feed.

        Args:
            source: Audio source - "pulse", "alsa:hw:0", or "file:/path"
            sample_rate: Audio sample rate
            buffer_size: FFT buffer size
            num_bands: Number of spectrum bands
            onset_threshold: Threshold for beat detection (0-1)
            min_beat_interval: Minimum seconds between beats
        """
        self.source = source
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.num_bands = num_bands
        self.onset_threshold = onset_threshold
        self.min_beat_interval = min_beat_interval

        # State
        self.bpm: Optional[float] = None
        self.beat_onset: bool = False
        self.beat_phase: float = 0.0
        self.spectrum: Optional[np.ndarray] = None
        self.volume: float = 0.0

        # Beat detection state
        self._last_beat_time: float = 0.0
        self._beat_intervals: List[float] = []
        self._bass_history: List[float] = []
        self._bass_avg: float = 0.0

        # Process
        self._process: Optional[asyncio.subprocess.Process] = None
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

    def _build_capture_command(self) -> List[str]:
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
        """Read audio data and analyze."""
        bytes_per_sample = 2  # 16-bit audio
        bytes_needed = self.buffer_size * bytes_per_sample

        try:
            while self._running and self._process and self._process.returncode is None:
                data = await self._process.stdout.read(bytes_needed)
                if not data:
                    await asyncio.sleep(0.01)
                    continue

                # Convert bytes to samples
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

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
        # Compute FFT
        window = np.hanning(len(samples))
        fft = np.abs(np.fft.rfft(samples * window))

        # Volume (RMS)
        self.volume = float(np.sqrt(np.mean(samples ** 2)))

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

        # Normalize spectrum
        max_val = np.max(self.spectrum)
        if max_val > 0:
            self.spectrum = self.spectrum / max_val

        # Beat detection using bass energy
        bass_energy = float(np.mean(self.spectrum[:3])) if self.spectrum is not None else 0

        # Maintain running average for adaptive threshold
        self._bass_history.append(bass_energy)
        if len(self._bass_history) > 43:  # ~1 second at 43 fps
            self._bass_history.pop(0)
        self._bass_avg = np.mean(self._bass_history) if self._bass_history else 0

        # Detect beat: bass energy spike above threshold and average
        now = time.time()
        time_since_last = now - self._last_beat_time

        threshold = max(self.onset_threshold, self._bass_avg * 1.5)
        is_beat = (
            bass_energy > threshold and
            time_since_last > self.min_beat_interval
        )

        if is_beat:
            self.beat_onset = True
            self._last_beat_time = now

            # Update BPM estimate
            if time_since_last < 2.0:  # Only use reasonable intervals
                self._beat_intervals.append(time_since_last)
                # Keep last 8 intervals
                if len(self._beat_intervals) > 8:
                    self._beat_intervals.pop(0)

                if len(self._beat_intervals) >= 4:
                    median_interval = float(np.median(self._beat_intervals))
                    if median_interval > 0:
                        self.bpm = 60.0 / median_interval
                        # Clamp to reasonable range
                        self.bpm = float(np.clip(self.bpm, 60, 200))
        else:
            self.beat_onset = False

        # Update beat phase (0-1 position within beat)
        if self.bpm and self.bpm > 0:
            beat_duration = 60.0 / self.bpm
            self.beat_phase = (time_since_last % beat_duration) / beat_duration
        else:
            self.beat_phase = 0.0

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
            bpm=self.bpm,
            beat_onset=self.beat_onset,
            beat_phase=self.beat_phase,
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
        self._last_beat_time = 0.0
        self._start_time = 0.0
        self._running = False

    async def start(self) -> None:
        """Start mock audio feed."""
        self._running = True
        self._start_time = time.time()
        self._last_beat_time = self._start_time
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
        beat_duration = 60.0 / self.bpm
        time_since_last = now - self._last_beat_time

        # Check if we hit a new beat
        beat_onset = False
        if time_since_last >= beat_duration:
            beat_onset = True
            self._last_beat_time = now
            time_since_last = 0.0

        # Calculate phase
        beat_phase = (time_since_last % beat_duration) / beat_duration

        # Generate fake spectrum (pulsing with beat)
        intensity = 1.0 - beat_phase  # Decay after beat
        spectrum = np.random.rand(16).astype(np.float32) * 0.3 + intensity * 0.7
        spectrum[:3] *= 1.5 if beat_onset else 1.0  # Boost bass on beat

        return AudioInput(
            bpm=self.bpm,
            beat_onset=beat_onset,
            beat_phase=beat_phase,
            spectrum=spectrum,
            volume=0.5 + intensity * 0.3,
            bass=float(np.mean(spectrum[:3])),
            mids=float(np.mean(spectrum[3:10])),
            highs=float(np.mean(spectrum[10:])),
        )

    @property
    def is_running(self) -> bool:
        return self._running
