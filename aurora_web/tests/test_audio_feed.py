"""Tests for AudioFeed class."""

import numpy as np
import pytest
import asyncio
import time

from aurora_web.inputs.audio_feed import AudioFeed, AudioInput, MockAudioFeed, BeatTracker, Onset, OnsetTracker


class TestAudioInput:
    """Tests for AudioInput dataclass."""

    def test_default_values(self):
        """AudioInput should have sensible defaults."""
        audio = AudioInput()
        assert audio.bpm is None
        assert audio.beat_onset is False
        assert audio.beat_phase == 0.0
        assert audio.beat_index == 0
        assert audio.bar_phase == 0.0
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
            beat_index=2,
            bar_phase=0.625,
            spectrum=spectrum,
            volume=0.8,
            bass=0.9,
            mids=0.5,
            highs=0.3,
        )
        assert audio.bpm == 120.0
        assert audio.beat_onset is True
        assert audio.beat_phase == 0.5
        assert audio.beat_index == 2
        assert audio.bar_phase == 0.625
        assert audio.volume == 0.8


class TestBeatTracker:
    """Tests for BeatTracker class."""

    def test_initialization(self):
        """BeatTracker should initialize with defaults."""
        tracker = BeatTracker()
        assert tracker.bpm == 120.0
        assert tracker.beat_onset is False
        assert tracker.beat_phase == 0.0
        assert tracker.beat_index == 0
        assert tracker.bar_phase == 0.0

    def test_reset(self):
        """Reset should clear all state."""
        tracker = BeatTracker()
        # Advance phase
        fft = np.ones(1025, dtype=np.float32)
        for _ in range(10):
            tracker.update(fft, 0.05)
        tracker.reset()
        assert tracker.bpm == 120.0
        assert tracker.beat_phase == 0.0
        assert tracker.beat_index == 0
        assert tracker.bar_phase == 0.0

    def test_phase_advances(self):
        """Phase should advance with dt at the current BPM."""
        tracker = BeatTracker()
        fft = np.ones(1025, dtype=np.float32) * 0.01  # Quiet signal
        tracker.update(fft, 0.0)  # Init prev_fft
        tracker.update(fft, 0.5)  # 0.5s at 120 BPM = 1 beat
        # Phase should have advanced by ~1 beat
        assert tracker.bar_phase > 0.0

    def test_beat_index_cycles(self):
        """beat_index should cycle 0-3 over a full bar."""
        tracker = BeatTracker()
        fft = np.ones(1025, dtype=np.float32) * 0.01
        # At 120 BPM, one beat = 0.5s, one bar = 2s
        # Step through in small increments
        tracker.update(fft, 0.0)  # Init prev_fft

        seen_indices = set()
        for _ in range(100):
            tracker.update(fft, 0.025)  # 2.5s total = 1.25 bars
            seen_indices.add(tracker.beat_index)

        assert seen_indices == {0, 1, 2, 3}

    def test_bar_phase_range(self):
        """bar_phase should always be in [0, 1)."""
        tracker = BeatTracker()
        fft = np.ones(1025, dtype=np.float32) * 0.01
        tracker.update(fft, 0.0)

        for _ in range(200):
            tracker.update(fft, 0.02)
            assert 0.0 <= tracker.bar_phase < 1.0
            assert 0.0 <= tracker.beat_phase < 1.0
            assert 0 <= tracker.beat_index <= 3

    def test_onset_nudges_phase(self):
        """Detected onset should nudge phase toward nearest beat."""
        tracker = BeatTracker()
        n = 1025
        # Create two FFT frames with big spectral change to trigger onset
        fft_quiet = np.ones(n, dtype=np.float32) * 0.01
        fft_loud = np.ones(n, dtype=np.float32) * 10.0

        # Build up flux statistics with quiet frames
        for _ in range(50):
            tracker.update(fft_quiet, 0.01)

        # Record phase before onset
        phase_before = tracker._phase

        # Big spectral change should trigger onset and nudge phase
        tracker.update(fft_loud, 0.01)
        # Phase should still be valid
        assert 0.0 <= tracker._phase < 4.0


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
        assert feed.beat_index == 0
        assert feed.bar_phase == 0.0

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

    def test_analyze_updates_beat_tracker(self):
        """_analyze should update beat tracker state."""
        feed = AudioFeed()
        n_samples = 2048
        t = np.linspace(0, n_samples / 44100, n_samples)
        samples = (np.sin(2 * np.pi * 100 * t) * 0.5).astype(np.float32)

        # Run several frames
        for _ in range(10):
            feed._analyze(samples)

        # Beat tracker should have been running (BPM set from tracker)
        assert feed.bpm is not None
        assert 60 <= feed.bpm <= 200
        assert 0.0 <= feed.beat_phase < 1.0
        assert 0 <= feed.beat_index <= 3
        assert 0.0 <= feed.bar_phase < 1.0

    def test_get_input_returns_audio_input(self):
        """get_input should return AudioInput instance."""
        feed = AudioFeed()
        result = feed.get_input()
        assert isinstance(result, AudioInput)
        assert result.beat_index == 0
        assert result.bar_phase == 0.0

    def test_get_input_includes_bar_fields(self):
        """get_input should include beat_index and bar_phase."""
        feed = AudioFeed()
        # Run some analysis
        n_samples = 2048
        t = np.linspace(0, n_samples / 44100, n_samples)
        samples = (np.sin(2 * np.pi * 100 * t) * 0.5).astype(np.float32)
        for _ in range(5):
            feed._analyze(samples)

        result = feed.get_input()
        assert isinstance(result.beat_index, int)
        assert isinstance(result.bar_phase, float)
        assert 0 <= result.beat_index <= 3
        assert 0.0 <= result.bar_phase <= 1.0

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

    def test_reset_state(self):
        """_reset_state should clear beat tracker and all state."""
        feed = AudioFeed()
        n_samples = 2048
        t = np.linspace(0, n_samples / 44100, n_samples)
        samples = (np.sin(2 * np.pi * 100 * t) * 0.5).astype(np.float32)

        for _ in range(10):
            feed._analyze(samples)

        feed._reset_state()
        assert feed.bpm is None
        assert feed.beat_onset is False
        assert feed.beat_index == 0
        assert feed.bar_phase == 0.0
        assert feed._beat_tracker._phase == 0.0


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
            assert 0 <= result.beat_index <= 3
            assert 0.0 <= result.bar_phase <= 1.0

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

    def test_bar_aware_mock(self):
        """MockAudioFeed should provide bar-aware values."""
        async def run_test():
            feed = MockAudioFeed(bpm=120.0)
            await feed.start()

            seen_indices = set()
            for _ in range(100):
                result = feed.get_input()
                seen_indices.add(result.beat_index)
                assert 0 <= result.beat_index <= 3
                assert 0.0 <= result.bar_phase <= 1.0
                time.sleep(0.025)  # 2.5s total > 1 bar at 120 BPM

            await feed.stop()

            # Should have cycled through all 4 beat indices
            assert seen_indices == {0, 1, 2, 3}

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


class TestOnsetTracker:
    """Tests for OnsetTracker class."""

    def _make_spectrum(self, val: float = 0.5) -> np.ndarray:
        return np.full(16, val, dtype=np.float32)

    def test_onset_quantization(self):
        """Onset at phase 1.5 should quantize to 16th-note position 6."""
        tracker = OnsetTracker()
        # phase=1.5 → raw_16th = 1.5*4 = 6.0 → position=6
        tracker.update(True, 1.0, 1.5, self._make_spectrum(), 0.5)
        assert len(tracker.active) == 1
        assert tracker.active[0].position == 6

    def test_onset_quantization_wraps(self):
        """Phase near 4.0 should wrap to position 0."""
        tracker = OnsetTracker()
        # phase=3.99 → raw_16th = 15.96 → round=16 → %16 = 0
        tracker.update(True, 1.0, 3.99, self._make_spectrum(), 0.5)
        assert tracker.active[0].position == 0

    def test_onset_quantization_various(self):
        """Check a few phase→position mappings."""
        cases = [
            (0.0, 0),    # raw=0
            (0.25, 1),   # raw=1
            (1.0, 4),    # raw=4
            (2.0, 8),    # raw=8
            (3.0, 12),   # raw=12
        ]
        for phase, expected_pos in cases:
            tracker = OnsetTracker()
            tracker.update(True, 1.0, phase, self._make_spectrum(), 0.5)
            assert tracker.active[0].position == expected_pos, f"phase={phase}"

    def test_envelope_grows_to_max(self):
        """Envelope should grow to max_envelope_frames then stop."""
        tracker = OnsetTracker(max_envelope_frames=4)
        tracker.update(True, 1.0, 0.5, self._make_spectrum(), 0.8)
        assert len(tracker.active[0].envelope) == 1  # initial volume

        # Subsequent frames (no onset) should extend envelope
        for i in range(10):
            tracker.update(False, 0.0, 0.5 + 0.01 * (i + 1), self._make_spectrum(), 0.5)

        assert len(tracker.active[0].envelope) == 4  # capped at max

    def test_bar_boundary_clears_active(self):
        """When phase wraps from >3 to <1, active moves to last_bar."""
        tracker = OnsetTracker()
        # Add onset at phase 2.0
        tracker.update(True, 1.0, 2.0, self._make_spectrum(), 0.5)
        assert len(tracker.active) == 1
        assert len(tracker.last_bar) == 0

        # Advance to near end of bar
        tracker.update(False, 0.0, 3.5, self._make_spectrum(), 0.5)

        # Cross bar boundary
        tracker.update(False, 0.0, 0.1, self._make_spectrum(), 0.5)
        assert len(tracker.active) == 0
        assert len(tracker.last_bar) == 1
        assert tracker.last_bar[0].position == 8  # phase 2.0 → pos 8

    def test_deduplication_keeps_stronger(self):
        """Same 16th-note position should keep the stronger onset."""
        tracker = OnsetTracker()
        tracker.update(True, 0.5, 1.0, self._make_spectrum(), 0.5)
        assert tracker.active[0].strength == 0.5

        # Same position (phase=1.0 → pos 4), stronger
        tracker.update(True, 2.0, 1.0, self._make_spectrum(), 0.7)
        assert len(tracker.active) == 1
        assert tracker.active[0].strength == 2.0

    def test_deduplication_rejects_weaker(self):
        """Weaker onset at same position should be rejected."""
        tracker = OnsetTracker()
        tracker.update(True, 2.0, 1.0, self._make_spectrum(), 0.5)
        tracker.update(True, 0.5, 1.0, self._make_spectrum(), 0.3)
        assert len(tracker.active) == 1
        assert tracker.active[0].strength == 2.0

    def test_onset_grid(self):
        """onset_grid should reflect active onsets."""
        tracker = OnsetTracker()
        tracker.update(True, 0.8, 0.0, self._make_spectrum(), 0.5)   # pos 0
        tracker.update(True, 1.2, 1.0, self._make_spectrum(), 0.5)   # pos 4

        grid = tracker.onset_grid
        assert grid.shape == (16,)
        assert grid[0] == pytest.approx(0.8)
        assert grid[4] == pytest.approx(1.2)
        assert grid[1] == 0.0  # no onset here

    def test_latest_onset(self):
        """latest_onset should return the most recent age==0 onset."""
        tracker = OnsetTracker()
        tracker.update(True, 1.0, 0.5, self._make_spectrum(), 0.5)
        assert tracker.latest_onset is not None
        assert tracker.latest_onset.position == 2  # phase 0.5 → raw 2.0

        # Next frame without onset: all onsets aged, no latest
        tracker.update(False, 0.0, 0.6, self._make_spectrum(), 0.5)
        assert tracker.latest_onset is None

    def test_reset_clears_everything(self):
        """reset() should clear active, last_bar, and prev_phase."""
        tracker = OnsetTracker()
        tracker.update(True, 1.0, 2.0, self._make_spectrum(), 0.5)
        tracker.update(False, 0.0, 3.5, self._make_spectrum(), 0.5)
        tracker.update(False, 0.0, 0.1, self._make_spectrum(), 0.5)
        # Now last_bar has data
        assert len(tracker.last_bar) > 0

        tracker.reset()
        assert tracker.active == []
        assert tracker.last_bar == []
        assert tracker._prev_phase == 0.0

    def test_spectrum_snapshot_is_copy(self):
        """Onset spectrum should be a copy, not a reference."""
        tracker = OnsetTracker()
        spec = self._make_spectrum(0.5)
        tracker.update(True, 1.0, 1.0, spec, 0.5)
        spec[:] = 999.0  # mutate original
        assert tracker.active[0].spectrum[0] == pytest.approx(0.5)

    def test_phase_error_recorded(self):
        """phase_error should reflect distance from exact grid point."""
        tracker = OnsetTracker()
        # phase=1.1 → raw=4.4 → round=4 → error = 4.4 - 4 = 0.4
        tracker.update(True, 1.0, 1.1, self._make_spectrum(), 0.5)
        assert tracker.active[0].phase_error == pytest.approx(0.4, abs=0.01)
