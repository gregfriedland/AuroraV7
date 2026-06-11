"""Audio feed: capture process management + MusicAnalyzer pipeline."""

import numpy as np
import asyncio
import time
from dataclasses import dataclass

from aurora_web.inputs.music_analyzer import MusicAnalyzer, MusicFeatures


@dataclass
class AudioInput:
    """Audio analysis data passed to drawers."""
    bpm: float | None = None           # Current tempo estimate (60-200)
    beat_onset: bool = False              # True on beat hit
    beat_phase: float = 0.0               # 0.0-1.0 position within beat
    spectrum: np.ndarray | None = None # FFT bins (16 bands)
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
        buffer_size: int = 1024,
        beat_tracker: str = "internal",
        latency_ms: float = 60.0,
        source_lambda: float = 0.35,
    ):
        """Initialize audio feed.

        Args:
            source: Audio source - "pulse", "alsa:hw:0", "mac:<device>",
                "pipe:/path", or "file:/path"
            sample_rate: Audio sample rate
            buffer_size: Samples per analysis hop (~23 ms at 1024/44100)
            beat_tracker: "beatnet", "aubio", or "internal" (see ADR 0004)
            latency_ms: Capture-to-display latency compensated by the
                predictive beat oscillator
            source_lambda: DP-means cluster granularity (ADR 0005 knob 2)
        """
        self.source = source
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size

        self.analyzer = MusicAnalyzer(
            sample_rate=sample_rate,
            hop_size=buffer_size,
            beat_tracker=beat_tracker,
            latency_ms=latency_ms,
            source_lambda=source_lambda,
        )

        # Optional BeatNet subprocess (started in start(), ADR 0004)
        self._beatnet = None
        self._beatnet_requested = beat_tracker == "beatnet"
        self._ext_beat_times: list[float] = []

        # Legacy mirrors of the latest features (kept for old tests/drawers)
        self.bpm: float | None = None
        self.beat_onset: bool = False
        self.beat_phase: float = 0.0
        self.spectrum: np.ndarray | None = None
        self.volume: float = 0.0

        # Process
        self._process: asyncio.subprocess.Process | None = None
        self._running: bool = False
        self._task: asyncio.Task | None = None

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
        elif self.source.startswith("mac:"):
            # macOS capture (e.g. "mac:BlackHole 2ch"). Prefer sox/coreaudio:
            # ffmpeg's avfoundation input silently drops ~20% of audio
            # packets, which corrupts all tempo estimation.
            device = self.source[4:]
            import shutil
            if shutil.which("sox"):
                return [
                    "sox", "-q",
                    "-t", "coreaudio", device,
                    "-t", "raw",
                    "-r", str(self.sample_rate),
                    "-e", "signed", "-b", "16", "-c", "1",
                    "-",
                ]
            print("[AudioFeed] WARNING: sox not found; falling back to ffmpeg "
                  "avfoundation, which drops audio packets (brew install sox)")
            return [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-f", "avfoundation",
                "-i", f":{device}",
                "-f", "s16le",
                "-ar", str(self.sample_rate),
                "-ac", "1",
                "-",
            ]
        elif self.source.startswith("pipe:"):
            # Raw PCM FIFO (e.g. shairport-sync pipe)
            return ["cat", self.source[5:]]
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
            if self._beatnet_requested:
                try:
                    from aurora_web.core.beatnet_process import BeatNetManager
                    self._beatnet = BeatNetManager(self.sample_rate)
                    self._beatnet.start()
                except Exception as e:
                    print(f"[AudioFeed] BeatNet unavailable: {e}")
                    self._beatnet = None
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
                # readexactly accumulates a full analysis buffer; plain read()
                # returns tiny bursts that would be too short to analyze
                try:
                    data = await self._process.stdout.readexactly(bytes_needed)
                except asyncio.IncompleteReadError as e:
                    data = e.partial
                    if not data:
                        break  # EOF

                # Convert bytes to samples
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

                if len(samples) >= self.buffer_size // 2:
                    self._analyze(samples)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[AudioFeed] Read error: {e}")

    def _analyze(self, samples: np.ndarray) -> None:
        """Run one hop through the MusicAnalyzer pipeline."""
        if self._beatnet is not None:
            self._beatnet.feed(samples)
            for wall_t, is_downbeat in self._beatnet.poll():
                self._ext_beat_times.append(wall_t)
                if len(self._ext_beat_times) > 8:
                    self._ext_beat_times.pop(0)
                bpm = None
                if len(self._ext_beat_times) >= 3:
                    intervals = np.diff(self._ext_beat_times)
                    med = float(np.median(intervals))
                    if 0.25 <= med <= 1.5:
                        bpm = 60.0 / med
                self.analyzer.inject_beat(wall_t, bpm, is_downbeat)

        features = self.analyzer.process(samples)

        # Legacy mirrors for old drawers/tests
        self.volume = features.volume
        self.spectrum = features.bands
        self.bpm = features.bpm
        self.beat_onset = features.beat_now
        self.beat_phase = features.beat_phase

    def get_input(self) -> MusicFeatures:
        """Get the latest MusicFeatures snapshot for drawers."""
        return self.analyzer.features

    async def stop(self) -> None:
        """Stop audio capture."""
        self._running = False

        if self._beatnet is not None:
            self._beatnet.stop()
            self._beatnet = None

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except ProcessLookupError:
                pass  # Process already exited
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
