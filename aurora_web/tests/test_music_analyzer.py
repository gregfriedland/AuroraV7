"""Synthetic-signal tests for the MusicAnalyzer pipeline (ADR 0004/0005)."""

import numpy as np
import pytest

from aurora_web.inputs.music_analyzer import (
    HAVE_AUBIO,
    MusicAnalyzer,
    MusicFeatures,
    SourceDiscovery,
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
    """Bass bursts at the given tempo (3 ms attack ramp avoids clicks)."""
    n = int(duration_s * SR)
    t = np.arange(n) / SR
    period = 60.0 / bpm
    gate = (t % period) < burst_s
    decay = np.exp(-((t % period) / burst_s) * 3.0)
    ramp = np.minimum((t % period) / 0.003, 1.0)
    return (np.sin(2 * np.pi * freq * t) * gate * decay * ramp).astype(np.float32)


def hat_track(duration_s, bpm=120, burst_s=0.03):
    """High-passed noise bursts at the given tempo."""
    from scipy import signal as sps
    rng = np.random.default_rng(42)
    n = int(duration_s * SR)
    t = np.arange(n) / SR
    period = 60.0 / bpm
    phase = t % period
    gate = (phase < burst_s).astype(np.float32)
    ramp = np.clip(phase / 0.004, 0.0, 1.0) * np.clip((burst_s - phase) / 0.004, 0.0, 1.0)
    noise = rng.standard_normal(n).astype(np.float32)
    env = (noise * gate * np.clip(ramp, 0, 1)).astype(np.float32)
    sos = sps.butter(8, 5000 / (SR / 2), "highpass", output="sos")
    out = sps.sosfilt(sos, env).astype(np.float32)
    out /= max(np.max(np.abs(out)), 1e-6)
    return (out * 0.8).astype(np.float32)


def bass_tone_track(duration_s, freq=220.0, note_s=0.4, gap_s=0.1):
    """Repeated sustained bass-register tones with soft attacks."""
    n = int(duration_s * SR)
    t = np.arange(n) / SR
    period = note_s + gap_s
    phase = t % period
    gate = (phase < note_s).astype(np.float32)
    ramp = np.clip(phase / 0.02, 0.0, 1.0) * np.clip((note_s - phase) / 0.05, 0.0, 1.0)
    return (0.5 * np.sin(2 * np.pi * freq * t) * gate * np.clip(ramp, 0, 1)).astype(np.float32)


class TestKickOnsets:
    def test_kick_fires_on_kick_track(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, kick_track(8.0))
        kicks = sum(f.onset_kick for f in feats)
        assert kicks >= 10, f"expected kick onsets, got {kicks}"

    def test_kick_rare_on_hat_track(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, hat_track(8.0))
        kicks = sum(f.onset_kick for f in feats)
        assert kicks <= 4, f"kick onsets should be rare on a hat track, got {kicks}"

    def test_silence_no_onsets(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, np.zeros(SR * 3, dtype=np.float32))
        assert sum(f.onset_kick for f in feats) == 0


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
        start_t = feats[0].timestamp
        beat_times = [f.timestamp for f in feats
                      if f.beat_now and (f.timestamp - start_t) > 12.0]
        assert len(beat_times) >= 8, "too few predicted beats"
        period = 0.5
        errs = []
        for bt in beat_times:
            rel = (bt - start_t) % period
            errs.append(min(rel, period - rel))
        med = float(np.median(errs))
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


class TestSourceDiscovery:
    def test_nmf_activations_nonnegative_and_responsive(self):
        a, clock = make_analyzer()
        run_signal(a, clock, kick_track(6.0))
        sd = a.discovery
        assert np.all(sd.h >= 0)
        # peak activation during the kick track should beat silence
        hist = sd._h_hist
        h_active = float(np.max(hist.sum(axis=1)))
        run_signal(a, clock, np.zeros(SR * 3, dtype=np.float32))
        h_silent = float(np.sum(a.discovery.h))
        assert h_active > h_silent * 10

    def test_w_columns_unit_norm(self):
        a, clock = make_analyzer()
        run_signal(a, clock, kick_track(8.0))
        norms = np.linalg.norm(a.discovery.W, axis=0)
        assert np.allclose(norms, 1.0, atol=1e-3)

    def test_sources_appear_after_warmup(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, kick_track(6.0))
        assert feats[5].sources is None, "sources should be empty before first refresh"
        assert feats[-1].sources is not None, "sources should exist after warmup"
        assert len(feats[-1].sources) == 5
        assert np.all(feats[-1].sources >= 0) and np.all(feats[-1].sources <= 1)

    def test_kick_track_one_dominant_low_source(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, kick_track(15.0))
        f = feats[-1]
        # p95 activation per slot over the last 4 s: kicks are silent ~80%
        # of the time, so means are low by construction
        acts = np.percentile([g.sources for g in feats[-170:] if g.sources is not None],
                             95, axis=0)
        dominant = int(np.argmax(acts))
        assert acts[dominant] > 0.3, f"no dominant source: {acts}"
        # the dominant source of a 55 Hz kick should sit low in frequency
        assert f.source_centroid[dominant] < 0.45, \
            f"kick centroid {f.source_centroid[dominant]} not low"

    def test_kick_vs_hat_distinct_sources(self):
        a, clock = make_analyzer()
        sig = kick_track(15.0) + hat_track(15.0)
        feats = run_signal(a, clock, sig)
        valid = [g for g in feats[-170:] if g.sources is not None]
        acts = np.percentile([g.sources for g in valid], 95, axis=0)
        cents = feats[-1].source_centroid
        strong = np.where(acts > 0.25)[0]
        assert len(strong) >= 2, f"expected >=2 active sources, acts={acts}"
        # at least two strong sources far apart in frequency
        spread = cents[strong].max() - cents[strong].min()
        assert spread > 0.25, f"sources not spectrally separated: {cents[strong]}"

    def test_kick_vs_bass_tone_distinct(self):
        a, clock = make_analyzer()
        sig = kick_track(18.0) * 0.8 + bass_tone_track(18.0, freq=330.0) * 0.8
        feats = run_signal(a, clock, sig)
        valid = [g for g in feats[-170:] if g.sources is not None]
        acts = np.percentile([g.sources for g in valid], 95, axis=0)
        strong = np.where(acts > 0.25)[0]
        assert len(strong) >= 2, f"kick+tone should form >=2 sources, acts={acts}"

    def test_centroids_sorted_ascending(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, kick_track(10.0) + hat_track(10.0))
        cents = feats[-1].source_centroid
        assert cents is not None
        assert np.all(np.diff(cents) >= -1e-6), f"slots not sorted by centroid: {cents}"

    def test_per_chunk_budget(self):
        import time as _time
        a, clock = make_analyzer()
        sig = kick_track(3.0) + hat_track(3.0)
        chunks = [sig[i:i + HOP] for i in range(0, len(sig) - HOP, HOP)]
        for c in chunks[:20]:
            clock.advance(HOP_DT)
            a.process(c)
        t0 = _time.perf_counter()
        for c in chunks:
            clock.advance(HOP_DT)
            a.process(c)
        per_chunk = (_time.perf_counter() - t0) / len(chunks) * 1000
        assert per_chunk < 8.0, f"{per_chunk:.2f} ms per 23 ms chunk (too slow)"


class TestCompat:
    def test_bands_shape_and_range(self):
        a, clock = make_analyzer()
        feats = run_signal(a, clock, kick_track(2.0))
        f = feats[-1]
        assert f.bands.shape == (16,)
        assert np.all(f.bands >= 0) and np.all(f.bands <= 1)

    def test_audioinput_backcompat_fields(self):
        a, clock = make_analyzer()
        f = run_signal(a, clock, kick_track(1.0))[-1]
        assert f.spectrum is not None and len(f.spectrum) == 16
        assert isinstance(f.beat_onset, bool)
        for name in ("bpm", "beat_phase", "volume", "bass", "mids", "highs"):
            assert hasattr(f, name)

    def test_default_features_safe(self):
        f = MusicFeatures()
        assert f.spectrum is None and f.beat_onset is False
        assert f.sources is None
