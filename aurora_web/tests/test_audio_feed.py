"""Tests for AudioFeed class."""

import numpy as np
import pytest
import asyncio
import time

from aurora_web.inputs.audio_feed import AudioFeed, AudioInput, MockAudioFeed


class TestAudioInput:
    """Tests for AudioInput dataclass."""

    def test_default_values(self):
        """AudioInput should have sensible defaults."""
        audio = AudioInput()
        assert audio.bpm is None
        assert audio.beat_onset is False
        assert audio.beat_phase == 0.0
        assert audio.spectrum is None
        assert audio.volume == 0.0
        assert audio.bass == 0.0
        assert audio.mids == 0.0
        assert audio.highs == 0.0

    def test_custom_values(self):
        """AudioInput should accept custom values."""
        spectrum = np.array([0.5] * 16, dtype=np.float32)
        audio = AudioInput(
            bpm=120.0,
            beat_onset=True,
            beat_phase=0.5,
            spectrum=spectrum,
            volume=0.8,
            bass=0.9,
            mids=0.5,
            highs=0.3,
        )
        assert audio.bpm == 120.0
        assert audio.beat_onset is True
        assert audio.beat_phase == 0.5
        assert audio.volume == 0.8


class TestAudioFeed:
    """Tests for AudioFeed class."""

    def test_initialization(self):
        """AudioFeed should initialize with defaults."""
        feed = AudioFeed()
        assert feed.source == "pulse"
        assert feed.sample_rate == 44100
        assert feed.bpm is None
        assert feed.beat_onset is False
        assert feed.analyzer is not None

    def test_custom_initialization(self):
        """AudioFeed should accept custom parameters."""
        feed = AudioFeed(
            source="alsa:hw:0",
            sample_rate=48000,
            beat_tracker="internal",
            latency_ms=80.0,
        )
        assert feed.source == "alsa:hw:0"
        assert feed.sample_rate == 48000
        assert feed.analyzer.backend_name == "internal"
        assert feed.analyzer.oscillator.latency_s == 0.08

    def test_build_pulse_command(self):
        """Should build correct PulseAudio capture command."""
        feed = AudioFeed(source="pulse", sample_rate=44100)
        cmd = feed._build_capture_command()
        assert cmd[0] == "parec"
        assert "--format=s16le" in cmd
        assert "--rate=44100" in cmd

    def test_build_alsa_command(self):
        """Should build correct ALSA capture command."""
        feed = AudioFeed(source="alsa:hw:1", sample_rate=48000)
        cmd = feed._build_capture_command()
        assert cmd[0] == "arecord"
        assert "-D" in cmd
        assert "hw:1" in cmd

    def test_build_file_command(self):
        """Should build correct file playback command."""
        feed = AudioFeed(source="file:/path/to/audio.wav")
        cmd = feed._build_capture_command()
        assert cmd[0] == "ffmpeg"
        assert "/path/to/audio.wav" in cmd

    def test_invalid_source(self):
        """Should raise error for unknown source."""
        feed = AudioFeed(source="invalid:source")
        with pytest.raises(ValueError):
            feed._build_capture_command()

    def test_analyze_with_silence(self):
        """_analyze should handle silent audio."""
        feed = AudioFeed()
        samples = np.zeros(1024, dtype=np.float32)
        feed._analyze(samples)
        assert feed.volume == 0.0
        assert feed.beat_onset is False

    def test_analyze_with_signal(self):
        """_analyze should produce volume and a 16-band spectrum."""
        feed = AudioFeed()
        t = np.linspace(0, 1024 / 44100, 1024)
        samples = (np.sin(2 * np.pi * 100 * t) * 0.5).astype(np.float32)
        for _ in range(4):
            feed._analyze(samples)
        assert feed.volume > 0
        assert feed.spectrum is not None
        assert len(feed.spectrum) == 16

    def test_analyze_delegates_to_music_analyzer(self):
        """_analyze should update the MusicAnalyzer feature snapshot."""
        feed = AudioFeed()
        t = np.linspace(0, 1024 / 44100, 1024)
        samples = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
        feed._analyze(samples)
        f = feed.analyzer.features
        assert f.timestamp > 0
        assert f.volume == feed.volume

    def test_get_input_returns_music_features(self):
        """get_input should return a MusicFeatures snapshot."""
        from aurora_web.inputs.music_analyzer import MusicFeatures
        feed = AudioFeed()
        result = feed.get_input()
        assert isinstance(result, MusicFeatures)
        # old AudioInput API surface preserved
        for name in ("bpm", "beat_onset", "beat_phase", "spectrum",
                     "volume", "bass", "mids", "highs"):
            assert hasattr(result, name)

    def test_spectrum_normalization(self):
        """Spectrum should be normalized to 0-1 range."""
        feed = AudioFeed()
        # Generate signal with known frequency content
        t = np.linspace(0, 1024 / 44100, 1024)
        samples = (np.sin(2 * np.pi * 200 * t) * 0.8).astype(np.float32)
        for _ in range(4):
            feed._analyze(samples)

        if feed.spectrum is not None:
            assert np.all(feed.spectrum >= 0)
            assert np.all(feed.spectrum <= 1)


class TestMockAudioFeed:
    """Tests for MockAudioFeed class."""

    def test_initialization(self):
        """MockAudioFeed should initialize with BPM."""
        feed = MockAudioFeed(bpm=120.0)
        assert feed.bpm == 120.0
        assert not feed.is_running

    def test_start_stop(self):
        """MockAudioFeed should start and stop."""
        async def run_test():
            feed = MockAudioFeed(bpm=120.0)
            await feed.start()
            assert feed.is_running
            await feed.stop()
            assert not feed.is_running

        asyncio.run(run_test())

    def test_get_input_when_stopped(self):
        """get_input should return empty AudioInput when stopped."""
        feed = MockAudioFeed()
        result = feed.get_input()
        assert result.bpm is None
        assert result.beat_onset is False

    def test_get_input_when_running(self):
        """get_input should return valid AudioInput when running."""
        async def run_test():
            feed = MockAudioFeed(bpm=120.0)
            await feed.start()

            result = feed.get_input()
            assert result.bpm == 120.0
            assert result.spectrum is not None
            assert len(result.spectrum) == 16
            assert result.volume > 0

            await feed.stop()

        asyncio.run(run_test())

    def test_beat_detection_timing(self):
        """MockAudioFeed should trigger beats at correct intervals."""
        async def run_test():
            feed = MockAudioFeed(bpm=600.0)  # 10 beats per second for fast test
            await feed.start()

            beat_count = 0
            for _ in range(15):
                result = feed.get_input()
                if result.beat_onset:
                    beat_count += 1
                time.sleep(0.1)

            await feed.stop()

            # Should have detected at least 1 beat in 1.5 seconds at 600 BPM
            assert beat_count >= 1

        asyncio.run(run_test())

    def test_beat_phase(self):
        """Beat phase should progress from 0 to 1."""
        async def run_test():
            feed = MockAudioFeed(bpm=120.0)
            await feed.start()

            phases = []
            for _ in range(10):
                result = feed.get_input()
                phases.append(result.beat_phase)
                time.sleep(0.05)

            await feed.stop()

            # Phases should be between 0 and 1
            assert all(0 <= p <= 1 for p in phases)

        asyncio.run(run_test())

    def test_spectrum_values(self):
        """Spectrum should have reasonable values."""
        async def run_test():
            feed = MockAudioFeed(bpm=120.0)
            await feed.start()

            result = feed.get_input()
            assert result.spectrum is not None
            assert np.all(result.spectrum >= 0)
            assert np.all(result.spectrum <= 2)  # Some boost allowed
            assert result.bass >= 0
            assert result.mids >= 0
            assert result.highs >= 0

            await feed.stop()

        asyncio.run(run_test())
