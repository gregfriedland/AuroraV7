"""Synthetic-signal tests for the MusicAnalyzer pipeline (ADR 0004)."""

import numpy as np
import pytest

from aurora_web.inputs.music_analyzer import (
    HAVE_AUBIO,
    MusicAnalyzer,
    MusicFeatures,
)

SR = 44100
HOP = 1024
HOP_DT = HOP / SR


class FakeClock:
    """Deterministic clock advancing in lockstep with processed audio."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def make_analyzer(beat_tracker="internal", latency_ms=0.0):
    clock = FakeClock()
    a = MusicAnalyzer(SR, HOP, beat_tracker=beat_tracker,
                      latency_ms=latency_ms, clock=clock)
    return a, clock


def run_signal(analyzer, clock, samples):
    """Feed samples through in hop-sized chunks; return list of features."""
    out = []
    for i in range(0, len(samples) - HOP + 1, HOP):
        clock.advance(HOP_DT)
        out.append(analyzer.process(samples[i:i + HOP].astype(np.float32)))
    return out


def kick_track(duration_s, bpm=120, freq=55.0, burst_s=0.1):
    """Bass bursts at the given tempo."""
    n = int(duration_s * SR)
    t = np.arange(n) / SR
    period = 60.0 / bpm
    gate = (t % period) < burst_s
    # exponential decay within each burst, like a kick drum; 3 ms attack
    # ramp avoids broadband clicks at the gate edge
    decay = np.exp(-((t % period) / burst_s) * 3.0)
    ramp = np.minimum((t % period) / 0.003, 1.0)
    return (np.sin(2 * np.pi * freq * t) * gate * decay * ramp).astype(np.float32)


def hat_track(duration_s, bpm=120, burst_s=0.03):
    """High-frequency noise bursts at the given tempo."""
    rng = np.random.default_rng(42)
    n = int(duration_s * SR)
    t = np.arange(n) / SR
    period = 60.0 / bpm
    gate = (t % period) < burst_s
    noise = rng.standard_normal(n).astype(np.float32)
    # crude high-pass: difference filter applied a few times
    for _ in range(4):
        noise = np.diff(noise, prepend=noise[0])
    noise /= max(np.max(np.abs(noise)), 1e-6)
    ramp = np.minimum((t % period) / 0.002, 1.0)
    return (noise * gate * ramp * 0.8).astype(np.float32)


class TestBandOnsets:
    def test_kick_fires_kick_not_hat(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, kick_track(8.0))
        kicks = sum(f.onset_kick for f in feats)
        hats = sum(f.onset_hat for f in feats)
        assert kicks >= 10, f"expected kick onsets, got {kicks}"
        assert hats <= kicks // 4, f"hat onsets should be rare on a kick track, got {hats}"

    def test_hat_fires_hat_not_kick(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, hat_track(8.0))
        hats = sum(f.onset_hat for f in feats)
        kicks = sum(f.onset_kick for f in feats)
        assert hats >= 10, f"expected hat onsets, got {hats}"
        assert kicks <= hats // 4, f"kick onsets should be rare on a hat track, got {kicks}"

    def test_onset_strength_in_range(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, kick_track(4.0))
        for f in feats:
            assert 0.0 <= f.kick_strength <= 1.0

    def test_silence_no_onsets(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, np.zeros(SR * 3, dtype=np.float32))
        assert sum(f.onset_kick or f.onset_snare or f.onset_hat for f in feats) == 0


class TestBeatTracking:
    def test_internal_backend_converges_to_120(self):
        a, clock = make_analyzer(beat_tracker="internal")
        feats = run_signal(a, clock, kick_track(20.0, bpm=120))
        bpm = feats[-1].bpm
        assert bpm is not None, "BPM never estimated"
        assert abs(bpm - 120) < 6 or abs(bpm - 60) < 3 or abs(bpm - 240) < 12, \
            f"BPM {bpm} not near 120 (or octave)"

    def test_predicted_beats_align_with_clicks(self):
        a, clock = make_analyzer(beat_tracker="internal")
        feats = run_signal(a, clock, kick_track(25.0, bpm=120))
        # consider only the second half (after convergence)
        start_t = feats[0].timestamp
        beat_times = [f.timestamp for f in feats
                      if f.beat_now and (f.timestamp - start_t) > 12.0]
        assert len(beat_times) >= 8, "too few predicted beats"
        period = 0.5  # 120 BPM
        errs = []
        for bt in beat_times:
            # clicks happen at start_t + k*period (signal starts at first hop)
            rel = (bt - start_t) % period
            errs.append(min(rel, period - rel))
        med = float(np.median(errs))
        # within a hop and a half of the true click
        assert med < 0.06, f"median beat error {med*1000:.0f}ms"

    def test_beat_phase_advances(self):
        a, clock = make_analyzer(beat_tracker="internal")
        feats = run_signal(a, clock, kick_track(20.0, bpm=120))
        phases = [f.beat_phase for f in feats[-40:]]
        assert max(phases) > 0.7 and min(phases) < 0.3, "beat_phase not sweeping"

    def test_beat_in_bar_cycles_1_to_4(self):
        a, clock = make_analyzer(beat_tracker="internal")
        feats = run_signal(a, clock, kick_track(20.0, bpm=120))
        seen = {f.beat_in_bar for f in feats}
        assert seen <= {1, 2, 3, 4}
        assert len({f.beat_in_bar for f in feats[-200:]}) == 4

    @pytest.mark.skipif(not HAVE_AUBIO, reason="aubio not installed")
    def test_aubio_backend_estimates_tempo(self):
        a, clock = make_analyzer(beat_tracker="aubio")
        feats = run_signal(a, clock, kick_track(20.0, bpm=120))
        bpm = feats[-1].bpm
        # aubio's tempo estimate is octave-error-prone (hence the internal
        # default); just require a plausible musical tempo
        assert bpm is not None
        assert 40 <= bpm <= 240, f"bpm={bpm}"

    def test_external_injection_drives_oscillator(self):
        a, clock = make_analyzer(beat_tracker="internal")
        sig = np.zeros(SR * 6, dtype=np.float32)
        out = []
        next_inject = clock.t + 0.5
        for i in range(0, len(sig) - HOP + 1, HOP):
            clock.advance(HOP_DT)
            if clock.t >= next_inject:
                a.inject_beat(clock.t, 120.0, False)
                next_inject += 0.5
            out.append(a.process(sig[i:i + HOP]))
        assert out[-1].bpm is not None and abs(out[-1].bpm - 120) < 2
        assert any(f.beat_now for f in out[-86:]), "no predicted beats from injected tracker"


class TestLoudness:
    def test_monotonic_with_amplitude(self):
        lufs = []
        for amp in (0.05, 0.2, 0.8):
            a, clock = make_analyzer()
            t = np.arange(SR * 2) / SR
            sig = (amp * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
            feats = run_signal(a, clock, sig)
            lufs.append(feats[-1].lufs)
        assert lufs[0] < lufs[1] < lufs[2]

    def test_agc_normalizes_quiet_and_loud(self):
        norms = []
        for amp in (0.05, 0.8):
            a, clock = make_analyzer()
            t = np.arange(SR * 10) / SR
            # alternate loud/soft each second so AGC sees a range
            env = np.where((t % 2) < 1, 1.0, 0.3)
            sig = (amp * env * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
            feats = run_signal(a, clock, sig)
            loud_sections = [f.loudness for f in feats[-80:] if f.loudness > 0]
            norms.append(np.max(loud_sections))
        # after adaptation both reach a similar normalized peak
        assert abs(norms[0] - norms[1]) < 0.35, f"AGC peaks differ: {norms}"

    def test_silence_is_zero(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, np.zeros(SR * 2, dtype=np.float32))
        assert feats[-1].loudness == 0.0


class TestPitchAndExpressive:
    def test_steady_tone_pitch(self):
        a, clock = make_analyzer()
        t = np.arange(SR * 3) / SR
        sig = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        feats = run_signal(a, clock, sig)
        voiced = [f.f0_hz for f in feats[-40:] if f.pitch_confidence > 0.4]
        assert len(voiced) > 10, "pitch not detected"
        assert abs(np.median(voiced) - 440) < 15, f"f0={np.median(voiced)}"
        assert feats[-1].pitch_class == 9  # A

    def test_vibrato_detected(self):
        a, clock = make_analyzer()
        t = np.arange(SR * 6) / SR
        # 440 Hz with 6 Hz, +/-50 cent FM
        cents = 50 * np.sin(2 * np.pi * 6 * t)
        freq = 440 * 2 ** (cents / 1200)
        phase = 2 * np.pi * np.cumsum(freq) / SR
        sig = (0.5 * np.sin(phase)).astype(np.float32)
        feats = run_signal(a, clock, sig)
        amounts = [f.vibrato_amount for f in feats[-80:]]
        assert np.median(amounts) > 0.25, f"vibrato amount {np.median(amounts)}"
        rates = [f.vibrato_rate for f in feats[-80:] if f.vibrato_rate > 0]
        assert rates and 3.0 < np.median(rates) < 9.0, f"vibrato rate {np.median(rates) if rates else None}"

    def test_steady_tone_no_vibrato(self):
        a, clock = make_analyzer()
        t = np.arange(SR * 4) / SR
        sig = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        feats = run_signal(a, clock, sig)
        assert np.median([f.vibrato_amount for f in feats[-40:]]) < 0.15

    def test_tremolo_detected(self):
        a, clock = make_analyzer()
        t = np.arange(SR * 6) / SR
        env = 0.5 + 0.4 * np.sin(2 * np.pi * 6 * t)
        sig = (env * np.sin(2 * np.pi * 220 * t) * 0.5).astype(np.float32)
        feats = run_signal(a, clock, sig)
        amounts = [f.tremolo_amount for f in feats[-80:]]
        assert np.median(amounts) > 0.15, f"tremolo {np.median(amounts)}"

    def test_sustain_state_on_held_tone(self):
        a, clock = make_analyzer()
        t = np.arange(SR * 4) / SR
        sig = (0.5 * np.sin(2 * np.pi * 330 * t)).astype(np.float32)
        feats = run_signal(a, clock, sig)
        assert feats[-1].envelope_state in ("sustain", "decay")
        assert feats[-1].sustain_level > 0.3

    def test_release_to_idle_after_tone_stops(self):
        a, clock = make_analyzer()
        t = np.arange(SR * 2) / SR
        tone = 0.5 * np.sin(2 * np.pi * 330 * t)
        sig = np.concatenate([tone, np.zeros(SR * 2)]).astype(np.float32)
        feats = run_signal(a, clock, sig)
        assert feats[-1].envelope_state in ("idle", "release")


class TestTextureAndCompat:
    def test_bands_shape_and_range(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, kick_track(2.0))
        f = feats[-1]
        assert f.bands.shape == (16,)
        assert np.all(f.bands >= 0) and np.all(f.bands <= 1)

    def test_brightness_high_for_noise_low_for_bass(self):
        a, clock = make_analyzer()
        feats_n = run_signal(a, clock, hat_track(3.0, bpm=600, burst_s=0.09))
        bright_noise = np.median([f.brightness for f in feats_n[-20:] if f.volume > 0.01])
        a2, clock2 = make_analyzer()
        t = np.arange(SR * 3) / SR
        feats_b = run_signal(a2, clock2, (0.5 * np.sin(2 * np.pi * 60 * t)).astype(np.float32))
        bright_bass = np.median([f.brightness for f in feats_b[-20:]])
        assert bright_noise > bright_bass

    def test_noise_flatter_than_tone(self):
        rng = np.random.default_rng(0)
        a, clock = make_analyzer()
        feats_n = run_signal(a, clock, (0.3 * rng.standard_normal(SR * 2)).astype(np.float32))
        a2, clock2 = make_analyzer()
        t = np.arange(SR * 2) / SR
        feats_t = run_signal(a2, clock2, (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32))
        assert feats_n[-1].noisiness > feats_t[-1].noisiness

    def test_audioinput_backcompat_fields(self):
        a, clock = make_analyzer()
        f = run_signal(a, clock, kick_track(1.0))[-1]
        # old AudioInput API surface used by existing drawers
        assert f.spectrum is not None and len(f.spectrum) == 16
        assert isinstance(f.beat_onset, bool)
        for name in ("bpm", "beat_phase", "volume", "bass", "mids", "highs"):
            assert hasattr(f, name)

    def test_default_features_safe(self):
        f = MusicFeatures()
        assert f.spectrum is None and f.beat_onset is False
