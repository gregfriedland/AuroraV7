# ADR 0004: Music Feature Extraction and Visualization

**Status:** Accepted
**Date:** 2026-06-09

## Context

Aurora's audio path (ADR 0003) extracts only crude features: RMS volume, a
16-band normalized spectrum, and a bass-spike "beat" detector. The result
*reacts* to bass energy but does not feel *synced* to the music: flashes land
late (detection latency), miss beats without strong bass, and nothing tracks
tempo, bars, melody, or expressive playing.

This ADR defines the core feature set for music-reactive drawers, surveys how
each feature is extracted (classic method vs. state of the art), and records
the chosen architecture. Research summary sources are linked inline.

## Core Features

| # | Feature | Signals exposed to drawers |
|---|---------|---------------------------|
| 1 | Drum onsets | `onset_kick`, `onset_snare`, `onset_hat` (bool + strength 0-1) |
| 2 | Instrument notes | `note_on`, `f0_hz`, `pitch_class`, `pitch_confidence` |
| 3 | Overall volume | `loudness` (perceptual, auto-gained 0-1), `volume` (raw RMS) |
| 4 | Tempo | `bpm`, `beat_phase` (0-1 within beat), `beat_now` (predicted) |
| 5 | Measure/bar | `bar_phase` (0-1 within bar), `beat_in_bar` (1-4), `downbeat_now` |
| 6 | Expressive | `vibrato_amount/rate`, `tremolo_amount`, `bend_amount`, `envelope_state` (ADSR), `sustain_level` |
| 7 | Texture | `bands[16]` (auto-gained), `brightness` (centroid), `noisiness` (flatness) |

## Survey: how each feature is extracted

### 1. Drum / percussive onsets

- **Classic:** energy rise over a running average (what Aurora had). Cheap,
  misses soft onsets, fires on sustained bass.
- **Better classic (chosen):** *spectral flux* — half-wave-rectified increase
  in STFT magnitudes between frames — computed **per frequency band** so kick
  (≈40-130 Hz), snare (≈200-750 Hz + 2-5 kHz noise burst), and hats/cymbals
  (≥5 kHz) are separated. Combined with *adaptive whitening* (normalize each
  bin by its recent decaying maximum; [Stowell & Plumbley 2007](https://www.researchgate.net/publication/250824858_Adaptive_whitening_for_improved_real-time_audio_onset_detection))
  and causal peak-picking (local max + moving-mean threshold + minimum
  inter-onset interval; [FMP notebooks](https://www.audiolabs-erlangen.de/resources/MIR/FMP/C6/C6S1_PeakPicking.html)).
  This is what [ofxBeat](https://github.com/darrenmothersele/ofxBeat) and the
  [WLED audioreactive usermod](https://github.com/wled/WLED/blob/main/usermods/audioreactive/audio_reactive.cpp) do.
- **State of the art:** [SuperFlux](https://madmom.readthedocs.io/en/v0.16.1/modules/features/onsets.html)
  (Böck & Widmer 2013: max-filter along frequency suppresses vibrato false
  positives) and CNN onset detectors (madmom `CNNOnsetProcessor`). SuperFlux
  ideas (log-magnitude, frequency max-filter) are folded into our flux;
  CNN detectors are unnecessary for visualization.

### 2. Instrument notes: pitch + onset + volume

- **Classic (chosen):** YIN-family f0 tracking — `aubio.pitch("yinfft")`
  (spectral YIN, causal, <1% CPU) plus `aubio.notes` for MIDI-like
  note-on/velocity events. ([aubio](https://aubio.org/))
- **State of the art:** lightweight neural pitch — [SwiftF0](https://github.com/lars76/swift-f0)
  (95k-param CNN, ONNX) and [PESTO](https://arxiv.org/abs/2508.01488)
  (130k params, <5 ms latency, `pip install pesto-pitch`). Both Pi-5-capable;
  good upgrade path if yinfft proves noisy. [CREPE](https://github.com/maxrmorrison/torchcrepe)
  is heavier with no accuracy-per-FLOP advantage now.
- **Polyphonic transcription** ([basic-pitch](https://github.com/spotify/basic-pitch),
  Onsets&Frames): non-causal, ~2 s windows — not viable for <100 ms visuals.
  Monophonic f0 tracks the *dominant* voice; we accept that.

### 3. Overall volume / loudness

- **Classic:** RMS per chunk (kept as `volume`).
- **Chosen:** ITU-R BS.1770 / EBU R128 *momentary loudness* — K-weighting
  (two biquads, stateful `scipy.signal.sosfilt`) → 400 ms sliding mean-square
  ([pyloudnorm](https://github.com/csteinmetz1/pyloudnorm) implements the
  filters; we run our own ring buffer for streaming) — then **auto-gain
  (AGC)**: rolling 5th/95th-percentile normalization over ~20 s, gated below a
  noise floor, so the display works at any playback volume. Per-band AGC is
  what [WLED](https://mm.kno.wled.ge/soundreactive/sync/),
  [LedFx](https://github.com/LedFx/LedFx), and
  [Milkdrop](https://forums.winamp.com/forum/visualizations/milkdrop/309946-milkdrop2-beat-detection-auto-adjusting)
  (long-term-average relative levels) all do.

### 4. Tempo and beat phase — the "synced" problem

Reacting to detected onsets always *looks late*: detection lag (one hop +
peak-pick lookahead) plus capture latency lands flashes 50-150 ms behind the
hit. Everything serious about sync **predicts**:

- **Classic:** autocorrelation / comb-filterbank of the onset-strength
  envelope → tempo (Scheirer 1998); Ellis dynamic programming
  (librosa `beat_track`) is offline-only.
- **Real-time trackers:** [aubio.tempo](https://aubio.org/) (causal, tiny,
  known octave errors), [BTrack](https://github.com/adamstark/BTrack)
  (C++, predictive), madmom `DBNBeatTrackingProcessor(online=True)`
  (RNN, ~1 core, 100-200 ms perceived lag —
  [issue #382](https://github.com/CPJKU/madmom/issues/382)).
- **Chosen architecture — predictive phase oscillator** (PLL-style,
  [maxhaesslein's writeup](https://www.maxhaesslein.de/notes/real-time-beat-prediction-with-aubio/),
  [Beat-and-Tempo-Tracking](https://github.com/michaelkrzyzaniak/Beat-and-Tempo-Tracking)):
  a backend supplies (tempo, detected-beat times); the oscillator maintains
  (bpm, phase), **schedules upcoming beats on the clock**, applies
  slew-limited phase corrections when detections arrive, and compensates the
  configured pipeline latency (`latency_ms`). Drawers key off `beat_now` /
  `beat_phase`, which land *on* the beat instead of after it.

### 5. Downbeat / bar tracking

- **State of the art (chosen, optional):** [BeatNet](https://github.com/mjhydri/BeatNet)
  (Heydari et al., [ISMIR 2021](https://arxiv.org/abs/2108.03576)) — causal
  CRNN + particle filter, joint beat/downbeat/meter, streaming mode; the only
  packaged real-time downbeat tracker. PyTorch + madmom dependency → runs in a
  **separate process**, config-gated (`beat_tracker: beatnet`), graceful
  fallback when unavailable. Successors (BeatNet+,
  [zero-latency tracking, TISMIR 2024](https://transactions.ismir.net/articles/10.5334/tismir.189))
  to watch.
- **Heuristic fallback (always available):** accumulate kick-onset strength
  into 4 beat-phase bins over ~8 bars and rotate so the strongest accent is
  beat 1 (accent-pattern method à la Klapuri/Goto). Occasionally locks to
  beat 3; visually acceptable.
- Offline SOTA (madmom DBN downbeats, [Beat This!](https://archives.ismir.net/ismir2022/paper/000019.pdf))
  is non-causal — not usable live.

### 6. Expressive features (vibrato, tremolo, sustain, bends)

No turnkey real-time library exists; all are light post-processing on the f0
and amplitude streams ([RT vibrato detection](https://hajim.rochester.edu/ece/sites/zduan/teaching/ece472/projects/2015/Zhang_Liu_paper.pdf)):

- **Vibrato:** band-pass the f0-in-cents track at 4-8 Hz (stateful biquad);
  amount = modulation energy ratio, rate = zero-crossing rate.
- **Tremolo:** same on the amplitude envelope at 4-10 Hz.
- **Bend/portamento:** sustained |df0/dt| of 50-800 cents/s with no
  intervening onset.
- **Sustain/ADSR:** envelope follower (fast attack ~5 ms, slow release
  ~100 ms) + state machine: onset → attack → decay → sustain (flat env,
  stable f0) → release.

### 7. Texture / per-band energy

- 16 log-spaced bands from one rfft per hop, per-band AGC + asymmetric
  attack/decay smoothing (the universal visualizer recipe —
  [scottlawsonbc](https://github.com/scottlawsonbc/audio-reactive-led-strip),
  [essay on the pitfalls](https://scottlawsonbc.com/post/audio-led)).
- Spectral flatness (noisiness) and centroid (brightness) per frame.
- Harmonic/percussive separation (HPSS): real-time median-filter variants
  exist ([Real-Time-HPSS](https://github.com/sevagh/Real-Time-HPSS),
  [FluCoMa](https://learn.flucoma.org/reference/hpss/)) at ~200-400 ms
  latency; deferred — band heuristics cover current needs. Neural source
  separation (Demucs/Spleeter) is far from real-time on a Pi
  ([benchmarks](https://www.linuxlinks.com/machine-learning-linux-demucs-music-source-separation/2/)); rejected.

## Decision

A `MusicAnalyzer` pipeline (`aurora_web/inputs/music_analyzer.py`) consumes
PCM chunks from `AudioFeed` (capture stays per ADR 0003) and produces a
`MusicFeatures` snapshot per hop:

```
PCM (1024 samples ≈ 23 ms) ─→ rfft once
  ├─ BandEnergies      bands[16], bass/mids/highs, brightness, noisiness (AGC'd)
  ├─ MultiBandOnsets   kick/snare/hat flux → whiten → peak-pick
  ├─ LoudnessMeter     K-weighting → 400 ms momentary → AGC
  ├─ BeatTracker       backend (beatnet|aubio|internal) → predictive oscillator
  │                      → bpm, beat_phase, beat_now, bar_phase, beat_in_bar, downbeat_now
  ├─ PitchTracker      aubio yinfft + notes → f0, pitch_class, confidence, note_on
  └─ ExpressiveFeatures vibrato, tremolo, bend, ADSR state, sustain
```

- **Dependencies:** `aubio-ledfx` (the maintained aubio fork; plain `aubio`
  fails to build on Python 3.14 — verified working on both the Mac dev
  machine and the Pi). aubio imports are lazy; every aubio-backed component
  has a numpy fallback so the engine works without it. BeatNet+torch is an
  optional extra (`pip install -e ".[beatnet]"`), lazy-imported inside its
  subprocess only.
- **Backward compatibility:** `MusicFeatures` carries all old `AudioInput`
  fields; existing drawers keep working.
- **SignalGrid drawer** visualizes every signal in a fixed grid (rows =
  feature class, columns = band/beat position) — serves as both a debug
  surface and a reference for drawer authors.

## SignalGrid Layout (32×18)

| Rows | Section | What it shows |
|------|---------|---------------|
| 0–5 | Band energy | 16 GEQ columns, 40 Hz (left) → 16 kHz (right). Height = per-band auto-gained energy, so quiet bands get full visual range and the display is volume-independent. Fast attack / slow release. |
| 7–8 | Drum onsets | Three cells — kick \| snare \| hat. Flash on a spectral-flux onset in that band, brightness = hit strength, decay rate set by the `decay` setting. *Reactive*: lights when the hit happened. |
| 10–12 | Note box | One box per note, alive for the note's whole life. Onset: appears at the note's frequency (log x, A1 55 Hz → A6 1760 Hz). Sustain: holds, brightness tracking the envelope. Bend/vibrato: slides/wobbles in x following the live f0 (deviation from the onset pitch, magnified ~18 cents/px so a 50-cent vibrato is visible). Release or short note: fades at the decay rate. Expression is shown *in the note's behavior*, not as separate indicators. |
| 14–15 | Beat / bar | *Predictive*: four full-width boxes = beats 1–4 of the bar. The current beat lights when the oscillator's scheduled beat lands (on the beat, not after detection) and fades; downbeat (beat 1) uses the brightest palette slot. |
| 17 | Loudness | K-weighted loudness (BS.1770 weighting, 150 ms window — shortened from the 400 ms broadcast standard to avoid visible display lag), auto-gained 0–1. |

Reading tip: the onset row shows what *just happened*; the beat row shows
what is *about to happen*. Disagreement between them is usually syncopation,
not a bug. All sections consume the same `MusicFeatures` snapshot available
to every drawer — SignalGrid is the reference for which signals are worth
building richer visualizations on.

## CPU budget (Pi 5, 4×A76, measured/estimated per 23 ms hop)

| Component | Cost |
|---|---|
| rfft + bands + flux + AGC | ~0.1 ms (numpy) |
| K-weighting + loudness | ~0.02 ms (scipy sosfilt) |
| aubio tempo + pitch + notes | ~0.2 ms (C) |
| Expressive post-processing | ~0.05 ms |
| BeatNet (optional) | ~1 core, separate process |

## Consequences

- Drawers gain a rich, normalized, latency-compensated feature vocabulary;
  "flash on beat" becomes "flash on *predicted* beat".
- One new required dependency (`aubio-ledfx`), one optional heavy extra
  (BeatNet/torch). madmom (BeatNet's dependency) needs Cython+setuptools
  preinstalled and `--no-build-isolation` to build; its numpy compatibility
  is fragile — hence subprocess isolation and fallback chain.
- **BeatNet status (2026-06):** installable only via `pip install --no-deps
  BeatNet` + torch + librosa + matplotlib + pyaudio + madmom@git (the PyPI
  package pins numba 0.54, unbuildable on modern Python). With numpy-2 shims
  the model loads and runs, but `mode='realtime'` (marked experimental
  upstream) emits no beat events on test signals — its particle filter
  degenerates (NaN weights). The `beatnet` backend therefore exists and is
  wired, but the aubio backend remains the working default until upstream
  fixes realtime mode (BeatNet+ / TISMIR-2024 successors are the path to
  watch).
- AGC means visuals are volume-independent but absolute level is lost;
  raw `volume` remains available.
- The downbeat heuristic can lock onto beat 3 in low-contrast music; BeatNet
  is the accurate (heavier) path.
