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
        assert feed.num_bands == 16
        assert feed.bpm is None
        assert feed.beat_onset is False

    def test_custom_initialization(self):
        """AudioFeed should accept custom parameters."""
        feed = AudioFeed(
            source="alsa:hw:0",
            sample_rate=48000,
            num_bands=32,
            onset_threshold=0.7,
        )
        assert feed.source == "alsa:hw:0"
        assert feed.sample_rate == 48000
        assert feed.num_bands == 32
        assert feed.onset_threshold == 0.7

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
        """_analyze should detect signal properties."""
        feed = AudioFeed()
        # Generate a simple sine wave
        t = np.linspace(0, 0.1, 1024)
        samples = (np.sin(2 * np.pi * 100 * t) * 0.5).astype(np.float32)
        feed._analyze(samples)
        assert feed.volume > 0
        assert feed.spectrum is not None
        assert len(feed.spectrum) == 16

    def test_analyze_beat_detection(self):
        """_analyze should detect beats from bass spikes."""
        feed = AudioFeed(onset_threshold=0.3, min_beat_interval=0.05)

        # Use 2048 samples for better FFT resolution
        # At 44100Hz sample rate, FFT bin spacing is ~21.5Hz
        # Bass bands 0-2 cover roughly 22-65Hz (logarithmic spacing)
        n_samples = 2048
        sample_rate = 44100
        t = np.linspace(0, n_samples / sample_rate, n_samples)

        # Build up a low bass_avg with high-frequency content (1kHz)
        # This frequency is well outside the bass range (bands 0-2)
        for _ in range(20):
            samples = (np.sin(2 * np.pi * 1000 * t) * 0.5).astype(np.float32)
            feed._analyze(samples)

        # Verify we have a low bass average established
        assert feed._bass_avg < 0.1, f"bass_avg should be near zero, got {feed._bass_avg}"

        # Wait past min_beat_interval
        time.sleep(0.1)

        # Now hit with a 40Hz bass signal - this lands in band 1 (22-43Hz)
        # After normalization, bass bands will have high energy
        bass_samples = (np.sin(2 * np.pi * 40 * t) * 0.95).astype(np.float32)
        feed._analyze(bass_samples)

        # Verify bass energy is above threshold
        bass_energy = float(np.mean(feed.spectrum[:3]))
        assert bass_energy > feed.onset_threshold, \
            f"bass_energy {bass_energy:.3f} should exceed threshold {feed.onset_threshold}"

        # Should have detected a beat onset
        assert feed.beat_onset is True, "beat_onset should be True after bass spike"
        assert feed.volume > 0.3

    def test_beat_not_detected_below_threshold(self):
        """beat_onset should be False when bass energy is below threshold."""
        feed = AudioFeed(onset_threshold=0.8, min_beat_interval=0.05)

        n_samples = 2048
        sample_rate = 44100
        t = np.linspace(0, n_samples / sample_rate, n_samples)

        time.sleep(0.1)  # Ensure min_beat_interval passes

        # Moderate bass signal - not strong enough to exceed 0.8 threshold
        # Use lower amplitude so normalized bass energy stays below threshold
        samples = (np.sin(2 * np.pi * 40 * t) * 0.3).astype(np.float32)
        # Add some high frequency to spread the energy
        samples += (np.sin(2 * np.pi * 1000 * t) * 0.7).astype(np.float32)
        feed._analyze(samples)

        # Bass energy should be below threshold due to energy spread
        bass_energy = float(np.mean(feed.spectrum[:3]))
        assert feed.beat_onset is False, \
            f"beat_onset should be False when bass_energy ({bass_energy:.3f}) < threshold ({feed.onset_threshold})"

    def test_beat_not_detected_within_min_interval(self):
        """beat_onset should be False when min_beat_interval hasn't passed."""
        feed = AudioFeed(onset_threshold=0.3, min_beat_interval=1.0)  # 1 second interval

        n_samples = 2048
        sample_rate = 44100
        t = np.linspace(0, n_samples / sample_rate, n_samples)

        # Establish low bass baseline first
        high_freq_samples = (np.sin(2 * np.pi * 1000 * t) * 0.5).astype(np.float32)
        for _ in range(20):
            feed._analyze(high_freq_samples)

        # First beat - should trigger
        time.sleep(0.1)
        bass_samples = (np.sin(2 * np.pi * 40 * t) * 0.95).astype(np.float32)
        feed._analyze(bass_samples)
        assert feed.beat_onset is True, "First beat should be detected"

        # Second beat immediately after - should NOT trigger (within 1s interval)
        feed._analyze(bass_samples)
        assert feed.beat_onset is False, \
            "beat_onset should be False when min_beat_interval (1.0s) hasn't passed"

    def test_beat_onset_resets_after_non_beat(self):
        """beat_onset should reset to False after a non-beat frame."""
        feed = AudioFeed(onset_threshold=0.3, min_beat_interval=0.05)

        n_samples = 2048
        sample_rate = 44100
        t = np.linspace(0, n_samples / sample_rate, n_samples)

        high_freq_samples = (np.sin(2 * np.pi * 1000 * t) * 0.5).astype(np.float32)
        bass_samples = (np.sin(2 * np.pi * 40 * t) * 0.95).astype(np.float32)

        # Establish low bass baseline first
        for _ in range(20):
            feed._analyze(high_freq_samples)

        # Trigger a beat
        time.sleep(0.1)
        feed._analyze(bass_samples)
        assert feed.beat_onset is True, "Beat should be detected"

        # Next frame with high frequency (no bass) - beat_onset should reset
        time.sleep(0.1)  # Wait past min_interval
        feed._analyze(high_freq_samples)
        assert feed.beat_onset is False, "beat_onset should reset to False after non-beat frame"

    def test_bpm_estimation_from_beats(self):
        """BPM should be estimated from beat intervals."""
        feed = AudioFeed(onset_threshold=0.3, min_beat_interval=0.05)

        n_samples = 2048
        sample_rate = 44100
        t = np.linspace(0, n_samples / sample_rate, n_samples)

        bass_samples = (np.sin(2 * np.pi * 40 * t) * 0.95).astype(np.float32)
        high_freq_samples = (np.sin(2 * np.pi * 1000 * t) * 0.5).astype(np.float32)

        # Simulate beats at ~120 BPM (0.5s intervals)
        beat_interval = 0.5
        detected_beats = 0

        for i in range(6):
            # Bass hit
            time.sleep(beat_interval if i > 0 else 0.1)
            feed._analyze(bass_samples)
            if feed.beat_onset:
                detected_beats += 1

            # Some non-beat frames
            for _ in range(3):
                feed._analyze(high_freq_samples)

        # Should have detected multiple beats
        assert detected_beats >= 4, f"Should detect at least 4 beats, got {detected_beats}"

        # BPM should be estimated (requires 4+ intervals)
        assert feed.bpm is not None, "BPM should be estimated after multiple beats"
        # At 0.5s intervals, expected BPM is 120
        assert 100 < feed.bpm < 140, f"BPM should be ~120, got {feed.bpm}"

    def test_adaptive_threshold(self):
        """Beat threshold should adapt to bass average."""
        feed = AudioFeed(onset_threshold=0.3, min_beat_interval=0.05)

        n_samples = 2048
        sample_rate = 44100
        t = np.linspace(0, n_samples / sample_rate, n_samples)

        # Build up high bass average with sustained bass
        bass_samples = (np.sin(2 * np.pi * 40 * t) * 0.6).astype(np.float32)
        for _ in range(30):
            feed._analyze(bass_samples)

        # bass_avg should now be elevated
        assert feed._bass_avg > 0.3, f"bass_avg should be elevated, got {feed._bass_avg}"

        # Wait for min_interval
        time.sleep(0.1)

        # Same bass level should NOT trigger beat (adaptive threshold = bass_avg * 1.5)
        feed._analyze(bass_samples)
        # The adaptive threshold should be higher than the bass energy
        adaptive_threshold = feed._bass_avg * 1.5
        bass_energy = float(np.mean(feed.spectrum[:3]))

        # If bass_energy <= adaptive_threshold, beat should not trigger
        if bass_energy <= adaptive_threshold:
            assert feed.beat_onset is False, \
                "beat_onset should be False when bass doesn't exceed adaptive threshold"

    def test_get_input_returns_audio_input(self):
        """get_input should return AudioInput instance."""
        feed = AudioFeed()
        result = feed.get_input()
        assert isinstance(result, AudioInput)

    def test_spectrum_normalization(self):
        """Spectrum should be normalized to 0-1 range."""
        feed = AudioFeed()
        # Generate signal with known frequency content
        t = np.linspace(0, 0.1, 2048)
        samples = (np.sin(2 * np.pi * 200 * t) * 0.8).astype(np.float32)
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
