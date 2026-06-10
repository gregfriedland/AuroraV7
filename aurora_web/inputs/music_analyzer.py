"""Real-time music feature extraction pipeline (ADR 0004).

Consumes mono float32 PCM chunks and produces a MusicFeatures snapshot per
hop. All components are causal and cheap enough for a Raspberry Pi 5:
one rfft per hop plus stateful filters.

aubio (the aubio-ledfx fork) is optional: tempo/pitch fall back to
pure-numpy implementations when it is unavailable.
"""

import time
from dataclasses import dataclass, field

import numpy as np
from scipy import signal as sps

try:
    import aubio
    HAVE_AUBIO = True
except Exception:  # pragma: no cover - import guard
    aubio = None
    HAVE_AUBIO = False


@dataclass
class MusicFeatures:
    """Feature snapshot passed to drawers (superset of the old AudioInput)."""

    timestamp: float = 0.0

    # Levels
    volume: float = 0.0            # raw RMS 0-1
    loudness: float = 0.0          # K-weighted momentary, AGC'd 0-1
    lufs: float = -70.0            # K-weighted momentary loudness, absolute

    # Texture
    bands: np.ndarray | None = None  # 16 AGC'd band energies 0-1
    bass: float = 0.0
    mids: float = 0.0
    highs: float = 0.0
    brightness: float = 0.0        # spectral centroid, 0-1 (log scale)
    noisiness: float = 0.0         # spectral flatness 0-1

    # Drum onsets
    onset_kick: bool = False
    onset_snare: bool = False
    onset_hat: bool = False
    kick_strength: float = 0.0
    snare_strength: float = 0.0
    hat_strength: float = 0.0

    # Notes / pitch
    note_on: bool = False
    f0_hz: float = 0.0
    pitch_class: int = -1          # 0-11 (C=0), -1 when unvoiced
    pitch_confidence: float = 0.0

    # Beat / bar (predictive)
    bpm: float | None = None
    beat_phase: float = 0.0        # 0-1 within beat
    beat_now: bool = False         # predicted beat lands this hop
    bar_phase: float = 0.0         # 0-1 within bar
    beat_in_bar: int = 1           # 1-4
    downbeat_now: bool = False

    # Expressive
    vibrato_amount: float = 0.0
    vibrato_rate: float = 0.0      # Hz
    tremolo_amount: float = 0.0
    bend_amount: float = 0.0       # signed, cents/s scaled to -1..1
    envelope_state: str = "idle"   # idle|attack|decay|sustain|release
    sustain_level: float = 0.0

    # ---- Backward compatibility with the old AudioInput ----
    @property
    def spectrum(self) -> np.ndarray | None:
        return self.bands

    @property
    def beat_onset(self) -> bool:
        return self.beat_now


class BandEnergies:
    """16 log-spaced band energies with per-band AGC and asymmetric smoothing."""

    NUM_BANDS = 16

    def __init__(self, sample_rate: int, fft_size: int):
        self.sample_rate = sample_rate
        freqs = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)
        edges = np.logspace(np.log10(40), np.log10(16000), self.NUM_BANDS + 1)
        self._slices = []
        for i in range(self.NUM_BANDS):
            idx = np.where((freqs >= edges[i]) & (freqs < edges[i + 1]))[0]
            if len(idx) == 0:  # guarantee at least one bin per band
                idx = np.array([np.searchsorted(freqs, edges[i])])
            self._slices.append(idx)
        self._freqs = freqs
        # AGC state: slow-decaying per-band maximum
        self._agc_max = np.full(self.NUM_BANDS, 1e-4)
        self.smoothed = np.zeros(self.NUM_BANDS, dtype=np.float32)

    NOISE_FLOOR = 1e-5
    AGC_DECAY = 0.999       # per hop (~16 s half-life at 43 hops/s)
    ATTACK = 0.6
    RELEASE = 0.15

    def process(self, mag: np.ndarray) -> np.ndarray:
        raw = np.array([float(np.mean(mag[s])) for s in self._slices])

        # AGC: track decaying max per band; freeze decay in silence
        active = raw > self.NOISE_FLOOR
        self._agc_max = np.where(
            active, np.maximum(raw, self._agc_max * self.AGC_DECAY), self._agc_max
        )
        norm = np.clip(raw / np.maximum(self._agc_max, 1e-6), 0.0, 1.0)

        # Asymmetric smoothing: fast attack, slow release
        coef = np.where(norm > self.smoothed, self.ATTACK, self.RELEASE)
        self.smoothed = (self.smoothed + coef * (norm - self.smoothed)).astype(np.float32)
        return self.smoothed

    def spectral_stats(self, mag: np.ndarray) -> tuple[float, float]:
        """Return (brightness, noisiness) from the magnitude spectrum."""
        power = mag ** 2
        total = float(np.sum(power))
        if total < 1e-10:
            return 0.0, 0.0
        centroid = float(np.sum(self._freqs * power) / total)
        # log-scale brightness: 100 Hz -> 0, 10 kHz -> 1
        brightness = float(np.clip(np.log10(max(centroid, 1.0) / 100.0) / 2.0, 0.0, 1.0))
        nz = power[power > 1e-12]
        flatness = float(np.exp(np.mean(np.log(nz))) / np.mean(nz)) if len(nz) else 0.0
        return brightness, float(np.clip(flatness, 0.0, 1.0))


class MultiBandOnsets:
    """Adaptive-whitened spectral flux onset detection in kick/snare/hat bands."""

    BANDS = {
        "kick": [(40, 130)],
        "snare": [(200, 750), (2000, 5000)],
        "hat": [(5000, 16000)],
    }
    WHITEN_DECAY = 0.997
    HISTORY = 43            # ~1 s of ODF history for the adaptive threshold
    MIN_IOI = 0.09          # seconds
    THRESH = 1.6            # odf must exceed mean * THRESH

    def __init__(self, sample_rate: int, fft_size: int):
        freqs = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)
        self._masks = {}
        for name, ranges in self.BANDS.items():
            mask = np.zeros(len(freqs), dtype=bool)
            for lo, hi in ranges:
                mask |= (freqs >= lo) & (freqs < hi)
            self._masks[name] = mask
        self._peak = np.full(len(freqs), 1e-6)
        self._global_max = 1e-6
        self._prev_white = np.zeros(len(freqs))
        self._odf_hist = {n: [] for n in self.BANDS}
        self._last_onset = {n: 0.0 for n in self.BANDS}
        self._armed = {n: True for n in self.BANDS}

    def process(self, mag: np.ndarray, now: float) -> dict:
        # Adaptive whitening: normalize each bin by its decaying peak.
        # Floor the peaks at a fraction of the global maximum so empty bands
        # don't amplify numerical noise into phantom onsets.
        self._global_max = max(float(np.max(mag)), self._global_max * self.WHITEN_DECAY, 1e-6)
        floor = 0.01 * self._global_max
        self._peak = np.maximum.reduce([mag, self._peak * self.WHITEN_DECAY,
                                        np.full_like(mag, floor)])
        white = mag / self._peak
        flux = np.maximum(0.0, white - self._prev_white)
        self._prev_white = white

        out = {}
        for name, mask in self._masks.items():
            odf = float(np.sum(flux[mask]))
            hist = self._odf_hist[name]
            mean = float(np.mean(hist)) if hist else 0.0
            std = float(np.std(hist)) if len(hist) > 4 else 1.0
            hist.append(odf)
            if len(hist) > self.HISTORY:
                hist.pop(0)

            if odf < mean:
                self._armed[name] = True

            # Energy gate: the band must hold a real share of spectral energy,
            # not just windowing leakage from transients in other bands
            band_level = float(np.mean(mag[mask]))
            fire = (
                self._armed[name]
                and odf > mean * self.THRESH
                and odf > 0.05
                and band_level > 0.02 * self._global_max
                and (now - self._last_onset[name]) > self.MIN_IOI
            )
            strength = 0.0
            if fire:
                self._armed[name] = False
                self._last_onset[name] = now
                strength = float(np.clip((odf - mean) / (3.0 * std + 1e-6), 0.0, 1.0))
            out[name] = (fire, strength, odf)
        return out


class LoudnessMeter:
    """K-weighted loudness with AGC normalization.

    BS.1770 momentary loudness uses a 400 ms window, but that lags visibly
    on a display; 150 ms keeps the K-weighting while feeling immediate.
    """

    WINDOW_S = 0.15
    GATE_LUFS = -60.0
    AGC_DECAY = 0.999

    def __init__(self, sample_rate: int, hop_size: int):
        self._sos = np.vstack([
            self._high_shelf(sample_rate, 1681.97, 3.99984, 0.7071752),
            self._high_pass(sample_rate, 38.13547, 0.5003270),
        ])
        self._zi = sps.sosfilt_zi(self._sos) * 0.0
        n = max(1, int(self.WINDOW_S * sample_rate / hop_size))
        self._ring = np.zeros(n)
        self._i = 0
        self._max_lufs = -30.0
        self._min_lufs = -55.0

    @staticmethod
    def _high_shelf(fs, f0, gain_db, Q):
        A = 10 ** (gain_db / 40)
        w0 = 2 * np.pi * f0 / fs
        alpha = np.sin(w0) / (2 * Q)
        cw = np.cos(w0)
        b = [A * ((A + 1) + (A - 1) * cw + 2 * np.sqrt(A) * alpha),
             -2 * A * ((A - 1) + (A + 1) * cw),
             A * ((A + 1) + (A - 1) * cw - 2 * np.sqrt(A) * alpha)]
        a = [(A + 1) - (A - 1) * cw + 2 * np.sqrt(A) * alpha,
             2 * ((A - 1) - (A + 1) * cw),
             (A + 1) - (A - 1) * cw - 2 * np.sqrt(A) * alpha]
        return np.array([b[0] / a[0], b[1] / a[0], b[2] / a[0], 1.0, a[1] / a[0], a[2] / a[0]]).reshape(1, 6)

    @staticmethod
    def _high_pass(fs, f0, Q):
        w0 = 2 * np.pi * f0 / fs
        alpha = np.sin(w0) / (2 * Q)
        cw = np.cos(w0)
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
        return np.array([b[0] / a[0], b[1] / a[0], b[2] / a[0], 1.0, a[1] / a[0], a[2] / a[0]]).reshape(1, 6)

    def process(self, samples: np.ndarray) -> tuple[float, float]:
        """Return (lufs, normalized_loudness 0-1)."""
        weighted, self._zi = sps.sosfilt(self._sos, samples, zi=self._zi)
        self._ring[self._i % len(self._ring)] = float(np.mean(weighted ** 2))
        self._i += 1
        ms = float(np.mean(self._ring)) if self._i >= len(self._ring) else float(
            np.mean(self._ring[: self._i])
        )
        lufs = -0.691 + 10 * np.log10(max(ms, 1e-12))

        if lufs > self.GATE_LUFS:
            # slowly forget extremes so the mapping adapts to the material
            self._max_lufs = max(lufs, self._max_lufs - 0.005)
            self._min_lufs = min(lufs, self._min_lufs + 0.005)
        span = max(self._max_lufs - self._min_lufs, 6.0)
        norm = float(np.clip((lufs - self._min_lufs) / span, 0.0, 1.0))
        if lufs <= self.GATE_LUFS:
            norm = 0.0
        return float(lufs), norm


class PredictiveBeatOscillator:
    """Phase-locked oscillator that schedules beats ahead of time.

    A backend supplies (bpm, detected beat timestamps). The oscillator keeps
    its own clock-based schedule and applies slew-limited corrections, so
    `beat_now` fires ON the beat instead of after detection latency.
    """

    SLEW = 0.25             # fraction of phase error corrected per detection
    MAX_STEP = 0.08         # max fraction of a period corrected at once
    BPM_BLEND = 0.15

    def __init__(self, latency_s: float = 0.06):
        self.latency_s = latency_s
        self.bpm: float | None = None
        self._next_beat: float | None = None
        self._beat_index = 0          # 0-3
        self._downbeat_offset = 0
        # accent histogram for the downbeat heuristic
        self._accents = np.zeros(4)

    @property
    def period(self) -> float | None:
        return 60.0 / self.bpm if self.bpm else None

    def on_detection(self, t: float, bpm: float | None) -> None:
        """Register a detected beat at capture time t (latency compensated)."""
        t -= self.latency_s
        if bpm and bpm > 0:
            self.bpm = bpm if self.bpm is None else (
                self.bpm + self.BPM_BLEND * (bpm - self.bpm)
            )
        if self.bpm is None:
            return
        period = self.period
        if self._next_beat is None:
            self._next_beat = t + period
            return
        # phase error to the NEAREST scheduled beat
        err = t - self._next_beat
        err -= round(err / period) * period
        step = float(np.clip(err * self.SLEW, -self.MAX_STEP * period, self.MAX_STEP * period))
        self._next_beat += step

    def on_kick(self, strength: float) -> None:
        """Feed kick accents into the downbeat histogram."""
        self._accents[self._beat_index] += strength
        if self._accents.sum() > 32:   # ~8 bars: re-estimate downbeat
            self._downbeat_offset = int(np.argmax(self._accents))
            self._accents *= 0.5

    def tick(self, now: float) -> tuple[bool, float, int, bool]:
        """Advance to `now`. Returns (beat_now, beat_phase, beat_in_bar, downbeat_now)."""
        if self.bpm is None or self._next_beat is None:
            return False, 0.0, 1, False
        period = self.period
        beat_now = False
        while now >= self._next_beat:
            beat_now = True
            self._next_beat += period
            self._beat_index = (self._beat_index + 1) % 4
        phase = float(np.clip(1.0 - (self._next_beat - now) / period, 0.0, 1.0))
        beat_in_bar = (self._beat_index - self._downbeat_offset) % 4 + 1
        downbeat = beat_now and beat_in_bar == 1
        return beat_now, phase, beat_in_bar, downbeat


class _AubioTempoBackend:
    """Beat detection via aubio.tempo."""

    def __init__(self, sample_rate: int, hop_size: int):
        self._tempo = aubio.tempo("default", hop_size * 4, hop_size, sample_rate)

    def process(self, chunk: np.ndarray, now: float) -> tuple[float | None, float | None]:
        """Return (bpm, detection_time or None) for this hop."""
        is_beat = self._tempo(chunk.astype(np.float32))
        bpm = float(self._tempo.get_bpm()) or None
        if bpm and not (40 <= bpm <= 220):
            bpm = None
        return bpm, (now if is_beat[0] else None)


class _InternalTempoBackend:
    """Pure-numpy fallback: autocorrelation of the onset-strength envelope."""

    BUF_S = 6.0

    def __init__(self, sample_rate: int, hop_size: int):
        self._hop_dt = hop_size / sample_rate
        self._env: list[float] = []
        self._maxlen = int(self.BUF_S / self._hop_dt)
        self._count = 0
        self._bpm: float | None = None

    def add_onset_strength(self, odf: float) -> None:
        self._env.append(odf)
        if len(self._env) > self._maxlen:
            self._env.pop(0)

    def process(self, kick_fired: bool, now: float) -> tuple[float | None, float | None]:
        self._count += 1
        if self._count % 21 == 0 and len(self._env) >= self._maxlen // 2:  # ~every 0.5 s
            env = np.array(self._env) - np.mean(self._env)
            ac = np.correlate(env, env, mode="full")[len(env) - 1:]
            lag_min = max(1, int(0.25 / self._hop_dt))   # 240 BPM
            lag_max = min(len(ac) - 1, int(1.0 / self._hop_dt))  # 60 BPM
            if lag_max > lag_min and ac[0] > 0:
                lags = np.arange(lag_min, lag_max)
                # mild preference for ~120 BPM
                prior = np.exp(-0.5 * ((60.0 / (lags * self._hop_dt) - 120) / 80) ** 2)
                best = lags[int(np.argmax(ac[lag_min:lag_max] * prior))]
                self._bpm = 60.0 / (best * self._hop_dt)
        return self._bpm, (now if kick_fired else None)


class PitchTracker:
    """Monophonic f0 + note events; aubio yinfft with numpy fallback."""

    def __init__(self, sample_rate: int, hop_size: int):
        self.sample_rate = sample_rate
        self.hop_size = hop_size
        self._pitch = None
        self._notes = None
        if HAVE_AUBIO:
            try:
                # "yin" rather than "yinfft": yinfft's get_confidence() returns
                # 0.0 even on clean tones in aubio-ledfx 0.4.11
                self._pitch = aubio.pitch("yin", hop_size * 2, hop_size, sample_rate)
                self._pitch.set_unit("Hz")
                self._pitch.set_tolerance(0.8)
                self._notes = aubio.notes("default", hop_size * 2, hop_size, sample_rate)
            except Exception:
                self._pitch = None
        self._prev_f0 = 0.0

    def process(self, chunk: np.ndarray) -> tuple[float, float, bool]:
        """Return (f0_hz, confidence, note_on)."""
        chunk32 = chunk.astype(np.float32)
        if self._pitch is not None:
            f0 = float(self._pitch(chunk32)[0])
            conf = float(self._pitch.get_confidence())
            note_on = False
            if self._notes is not None:
                ev = self._notes(chunk32)
                note_on = ev[0] > 0
            if not (30 <= f0 <= 4000):
                f0, conf = 0.0, 0.0
            return f0, conf, note_on

        # numpy fallback: autocorrelation pitch
        x = chunk - np.mean(chunk)
        if float(np.sqrt(np.mean(x ** 2))) < 1e-3:
            return 0.0, 0.0, False
        ac = np.correlate(x, x, mode="full")[len(x) - 1:]
        lag_min = int(self.sample_rate / 2000)
        lag_max = min(len(ac) - 1, int(self.sample_rate / 50))
        if lag_max <= lag_min:
            return 0.0, 0.0, False
        lag = lag_min + int(np.argmax(ac[lag_min:lag_max]))
        conf = float(np.clip(ac[lag] / (ac[0] + 1e-9), 0.0, 1.0))
        f0 = self.sample_rate / lag if conf > 0.3 else 0.0
        note_on = f0 > 0 and abs(f0 - self._prev_f0) > 0.06 * max(f0, 1.0)
        self._prev_f0 = f0
        return float(f0), conf, note_on


class ExpressiveFeatures:
    """Vibrato, tremolo, bends, and ADSR envelope state from f0/volume streams."""

    def __init__(self, hop_rate: float):
        self.hop_rate = hop_rate
        nyq = hop_rate / 2
        self._vib_sos = sps.butter(2, [min(4 / nyq, 0.9), min(8 / nyq, 0.95)], "bandpass", output="sos")
        self._vib_zi = sps.sosfilt_zi(self._vib_sos) * 0.0
        self._trem_sos = sps.butter(2, [min(4 / nyq, 0.9), min(10 / nyq, 0.95)], "bandpass", output="sos")
        self._trem_zi = sps.sosfilt_zi(self._trem_sos) * 0.0
        self._cents_hist: list[float] = []
        self._bp_hist: list[float] = []
        self._env = 0.0
        self._env_peak = 1e-6
        self.state = "idle"
        self._attack_flat_hops = 0
        self._last_cents = 0.0

    ATTACK_COEF = 0.9
    RELEASE_COEF = 0.05
    WIN = 43  # ~1 s

    def process(self, f0_hz: float, confidence: float, volume: float,
                note_on: bool, dt: float) -> dict:
        # --- f0 in cents (hold last value when unvoiced) ---
        if f0_hz > 0 and confidence > 0.4:
            cents = 1200.0 * np.log2(f0_hz / 55.0)
        else:
            cents = self._last_cents
        d_cents = (cents - self._last_cents) / max(dt, 1e-4)
        self._last_cents = cents

        # --- vibrato: 4-8 Hz modulation of the cents track ---
        bp, self._vib_zi = sps.sosfilt(self._vib_sos, [cents], zi=self._vib_zi)
        self._bp_hist.append(float(bp[0]))
        self._cents_hist.append(cents)
        if len(self._bp_hist) > self.WIN:
            self._bp_hist.pop(0)
            self._cents_hist.pop(0)
        bp_arr = np.array(self._bp_hist)
        vib_rms = float(np.sqrt(np.mean(bp_arr ** 2))) if len(bp_arr) > 8 else 0.0
        vibrato_amount = float(np.clip(vib_rms / 35.0, 0.0, 1.0))
        # rate from zero crossings of the bandpassed signal
        zc = int(np.sum(np.abs(np.diff(np.sign(bp_arr))) > 0)) if len(bp_arr) > 8 else 0
        vibrato_rate = zc / 2.0 / (len(bp_arr) / self.hop_rate) if len(bp_arr) > 8 else 0.0
        if vibrato_amount < 0.1:
            vibrato_rate = 0.0

        # --- tremolo: 4-10 Hz modulation of the volume envelope ---
        tp, self._trem_zi = sps.sosfilt(self._trem_sos, [volume], zi=self._trem_zi)
        trem_mod = abs(float(tp[0]))
        tremolo_amount = float(np.clip(trem_mod / (volume + 1e-3) * 4.0, 0.0, 1.0))

        # --- bend: sustained moderate f0 slope, no new note ---
        slope = float(np.clip(d_cents / 400.0, -1.0, 1.0))
        bend_amount = slope if (50.0 < abs(d_cents) < 800.0 and not note_on
                                and vibrato_amount < 0.3) else 0.0

        # --- ADSR envelope follower + state machine ---
        coef = self.ATTACK_COEF if volume > self._env else self.RELEASE_COEF
        self._env += coef * (volume - self._env)
        if note_on or (self.state in ("idle", "release") and volume > 0.02 and volume > self._env * 1.5):
            self.state = "attack"
            self._env_peak = max(volume, 1e-6)
            self._attack_flat_hops = 0
        elif self.state == "attack":
            if self._env > self._env_peak:
                self._env_peak = self._env
                self._attack_flat_hops = 0
            else:
                self._attack_flat_hops += 1
            if self._env < self._env_peak * 0.95:
                self.state = "decay"
            elif self._attack_flat_hops > 6:  # env stopped rising (~150 ms): held note
                self.state = "sustain"
        elif self.state == "decay":
            if self._env < self._env_peak * 0.1:
                self.state = "release"
            elif abs(volume - self._env) < 0.1 * self._env:
                self.state = "sustain"
        elif self.state == "sustain":
            if self._env < self._env_peak * 0.1:
                self.state = "release"
        elif self.state == "release":
            if self._env < 0.005:
                self.state = "idle"
        sustain_level = float(np.clip(self._env / max(self._env_peak, 1e-6), 0.0, 1.0))
        if self.state == "idle":
            sustain_level = 0.0

        return {
            "vibrato_amount": vibrato_amount,
            "vibrato_rate": float(vibrato_rate),
            "tremolo_amount": tremolo_amount,
            "bend_amount": float(bend_amount),
            "envelope_state": self.state,
            "sustain_level": sustain_level,
        }


class MusicAnalyzer:
    """Full analysis pipeline: PCM chunks in, MusicFeatures out."""

    FFT_SIZE = 2048

    def __init__(self, sample_rate: int = 44100, hop_size: int = 1024,
                 beat_tracker: str = "aubio", latency_ms: float = 60.0,
                 clock=time.time):
        self.sample_rate = sample_rate
        self.hop_size = hop_size
        self._clock = clock
        hop_rate = sample_rate / hop_size

        self.bands = BandEnergies(sample_rate, self.FFT_SIZE)
        self.onsets = MultiBandOnsets(sample_rate, self.FFT_SIZE)
        self.loudness = LoudnessMeter(sample_rate, hop_size)
        self.pitch = PitchTracker(sample_rate, hop_size)
        self.expressive = ExpressiveFeatures(hop_rate)
        self.oscillator = PredictiveBeatOscillator(latency_s=latency_ms / 1000.0)

        self.backend_name = beat_tracker
        self._aubio_backend = None
        self._internal_backend = _InternalTempoBackend(sample_rate, hop_size)
        if beat_tracker in ("aubio", "beatnet") and HAVE_AUBIO:
            try:
                self._aubio_backend = _AubioTempoBackend(sample_rate, hop_size)
            except Exception:
                self._aubio_backend = None
        # BeatNet detections are injected externally via inject_beat();
        # once any arrive, the local backend is suppressed
        self._external_beat: tuple[float, float | None, bool] | None = None
        self._external_active = False

        self._window = np.hanning(self.FFT_SIZE)
        self._fft_buf = np.zeros(self.FFT_SIZE, dtype=np.float32)
        self._kick_times: list[float] = []
        self.features = MusicFeatures()

    def inject_beat(self, t: float, bpm: float | None, is_downbeat: bool) -> None:
        """External tracker (BeatNet subprocess) reports a beat."""
        self._external_beat = (t, bpm, is_downbeat)
        self._external_active = True

    def _fix_tempo_octave(self) -> None:
        """Correct half-tempo octave errors using the kick-onset rate.

        Beat trackers (aubio especially) often lock to half the true tempo.
        If kicks consistently arrive at twice the tracked rate, double it.
        """
        osc = self.oscillator
        if osc.bpm is None or len(self._kick_times) < 6:
            return
        iois = np.diff(self._kick_times)
        iois = iois[(iois > 0.2) & (iois < 1.5)]
        if len(iois) < 4:
            return
        med_ioi = float(np.median(iois))
        ratio = (60.0 / osc.bpm) / med_ioi
        if 1.8 < ratio < 2.2 and osc.bpm * 2 <= 220:
            osc.bpm *= 2

    def process(self, chunk: np.ndarray) -> MusicFeatures:
        """Analyze one hop of mono float32 samples in [-1, 1]."""
        now = self._clock()
        f = MusicFeatures(timestamp=now)

        # Rolling FFT buffer (2048 window, hop-sized advance)
        n = len(chunk)
        self._fft_buf = np.roll(self._fft_buf, -n)
        self._fft_buf[-n:] = chunk
        mag = np.abs(np.fft.rfft(self._fft_buf * self._window))

        # Levels
        f.volume = float(np.sqrt(np.mean(chunk ** 2)))
        f.lufs, f.loudness = self.loudness.process(chunk)

        # Texture
        f.bands = self.bands.process(mag)
        f.bass = float(np.mean(f.bands[:3]))
        f.mids = float(np.mean(f.bands[3:10]))
        f.highs = float(np.mean(f.bands[10:]))
        f.brightness, f.noisiness = self.bands.spectral_stats(mag)

        # Onsets
        onsets = self.onsets.process(mag, now)
        f.onset_kick, f.kick_strength, kick_odf = onsets["kick"]
        f.onset_snare, f.snare_strength, _ = onsets["snare"]
        f.onset_hat, f.hat_strength, _ = onsets["hat"]

        # Beat tracking -> predictive oscillator
        self._internal_backend.add_onset_strength(kick_odf)
        bpm = detection = None
        if self._external_beat is not None:
            t, ext_bpm, is_down = self._external_beat
            self._external_beat = None
            bpm, detection = ext_bpm, t
            if is_down:
                # external tracker says this beat is the downbeat: align
                self.oscillator._downbeat_offset = (self.oscillator._beat_index + 1) % 4
        elif self._external_active:
            pass  # external tracker owns beat detection now
        elif self._aubio_backend is not None:
            bpm, detection = self._aubio_backend.process(chunk, now)
        else:
            bpm, detection = self._internal_backend.process(f.onset_kick, now)
        if detection is not None:
            self.oscillator.on_detection(detection, bpm)
        if f.onset_kick:
            self.oscillator.on_kick(f.kick_strength)
            self._kick_times.append(now)
            if len(self._kick_times) > 12:
                self._kick_times.pop(0)
            self._fix_tempo_octave()
        f.beat_now, f.beat_phase, f.beat_in_bar, f.downbeat_now = self.oscillator.tick(now)
        f.bpm = self.oscillator.bpm
        f.bar_phase = ((f.beat_in_bar - 1) + f.beat_phase) / 4.0

        # Pitch + expressive
        f.f0_hz, f.pitch_confidence, f.note_on = self.pitch.process(chunk)
        if f.f0_hz > 0:
            midi = 69 + 12 * np.log2(f.f0_hz / 440.0)
            f.pitch_class = int(round(midi)) % 12
        expr = self.expressive.process(
            f.f0_hz, f.pitch_confidence, f.volume, f.note_on,
            dt=self.hop_size / self.sample_rate,
        )
        f.vibrato_amount = expr["vibrato_amount"]
        f.vibrato_rate = expr["vibrato_rate"]
        f.tremolo_amount = expr["tremolo_amount"]
        f.bend_amount = expr["bend_amount"]
        f.envelope_state = expr["envelope_state"]
        f.sustain_level = expr["sustain_level"]

        self.features = f
        return f
