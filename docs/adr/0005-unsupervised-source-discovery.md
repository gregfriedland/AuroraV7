# ADR 0005: Unsupervised Instrument Source Discovery

**Status:** Accepted
**Date:** 2026-06-09

## Context

ADR 0004 extracted hand-engineered per-feature signals (multi-band drum
onsets, monophonic pitch, vibrato/tremolo heuristics) and the SignalGrid
drawer routed them to instrument-class rows with hand-written rules
(attack-within-120ms ⇒ "plucked", etc.). That approach hits a ceiling fast:
the rules encode our guesses about instruments instead of learning what the
*song* contains, and a monophonic pitch tracker can only follow one voice.

Greg proposed the generalization: **unsupervised online learning** over
spectral/envelope/rhythm features, so that a drum groove self-organizes
into source 1, a bass into source 2, a harmonica into source 3 — each
displayed on its own row, discovered as the song plays, with no labels and
no pretraining.

## Research

(Web research, ~20 sources; key citations.)

- Frame-level clustering alone cannot work: audio frames are **sums** of
  simultaneous sources, violating clustering's one-point-one-explanation
  assumption. The standard unsupervised tool for additive mixtures is
  **non-negative matrix factorization** (NMF) —
  [Smaragdis 2004 NMFD](https://www.merl.com/publications/docs/TR2004-104.pdf)
  introduced spectro-temporal templates for exactly the drum-extraction
  case; [Dittmar & Gärtner DAFx-2014](https://www.semanticscholar.org/paper/075eba57886593999b9bf04042e7e03d6d824921)
  demonstrated *real-time* frame-wise NMF with semi-adaptive bases;
  [Wu & Lerch ISMIR-2015](https://www.researchgate.net/publication/282859351)
  partially-fixed NMF for drums.
- **Online NMF** is embedded-cheap:
  [Lefèvre/Bach/Févotte 2011](https://arxiv.org/abs/1106.4198) — per-frame
  activation solve + sufficient-statistics dictionary updates with
  exponential forgetting (the Mairal online-dictionary-learning pattern).
- Identity via clustering of source *behavior*:
  [Battenberg 2012](https://ericbattenberg.com/publication/drum-separation/)
  (probabilistic spectral clustering of drum events),
  [Hazan/Marxer](https://arxiv.org/pdf/1502.00524) (incremental timbre
  clustering). **DP-means** (k-means that spawns a new cluster when a point
  is farther than λ from all centroids) discovers the number of sources
  online.
- Metrical position as a clustering feature appears under-explored in the
  literature. Per Greg: encode as an **ordinal-categorical 16th-note slot
  histogram** — an instrument repeating syncopated positions accumulates
  that signature, which continuous phase encodings blur.
- Transformers (HT-Demucs, BS-RoFormer, Beat This!) are the offline SOTA
  but are supervised, non-causal, and orders of magnitude over our compute
  budget; the unsupervised streaming problem is NMF+clustering territory.

## Decision

### Architecture (all numpy, per 256-sample hop = 5.8 ms, 172 frames/s)

```
audio ring buffer (capture chunks of 1024 are split into 4 hops)
  ├─ FFT, 2048-sample window → bands  < 500 Hz   (Δf 21.5 Hz; bass physics)
  └─ FFT,  512-sample window → bands ≥ 500 Hz    (11.6 ms; crisp transients)
        ↓ 40 log-spaced bands (40 Hz–16 kHz), log1p, per-band whitening
  v ∈ [0,1]⁴⁰
        ↓
  online KL-NMF  v ≈ W·h    W: 40×10 seeded, h warm-started, 3 mult. updates
        ↓ h (per hop)                 W: stats A,B w/ ~30 s forgetting,
        ↓                                sweep every 32 hops, silence-gated
  per-component descriptors (refresh ~0.5 s):
      timbre = W column · envelope stats of h_k(t) (burstiness p90/mean,
      rise sharpness, duty cycle) · 16-bin metrical histogram of h_k by
      16th-note slot (from the bar-locked beat oscillator, ADR 0004)
        ↓
  DP-means over the 10 descriptors (cosine, λ) → clusters = instruments
      greedy identity-matching across refreshes; top-5 by activity,
      ordered by spectral centroid (low→high)
        ↓
  MusicFeatures.sources[5], source_centroid[5], source_active[5]
        ↓
  SignalGrid: 5 source rows (box at centroid x, brightness = activation)
              + predictive beat-in-bar row
```

Dual-resolution rationale: frequency resolution is Δf = sample_rate/window.
A 40 Hz kick *physically requires* ≥ ~25 ms of signal (one cycle); high
frequencies are over-resolved by long windows and only suffer their time
smearing. Splitting at 500 Hz gives bass the resolution it needs and
transients the timing they need. Hop (update interval) is independent of
window length and set by compute only.

### What this replaces

Removed (superseded by the learned model): snare/hat onset detectors,
K-weighted loudness meter, monophonic pitch tracker (aubio yin),
vibrato/tremolo/bend/ADSR heuristics, the 16-band display spectrum as an
independent computation (the back-compat `MusicFeatures.spectrum` field is
now a free 16-band fold of the ML frontend's 40 whitened bands).

Kept: the **beat tracker** (ADR 0004's predictive bar-locked oscillator)
with the kick-band onset detector as its tempo/downbeat evidence, raw RMS
volume (NMF silence gate + back-compat), and the external-onset BeatBouncer
path.

## Tuning knobs

1. **Cluster refresh cadence & row stability** (default: re-cluster every
   0.5 s, greedy centroid matching across refreshes). Re-clustering 10
   descriptors is free; the risk is rows reshuffling. If rows flicker in
   practice, add hysteresis: a component must vote for its new cluster on
   two consecutive refreshes before moving.
2. **λ — cluster granularity** (default 0.45, config
   `inputs.audio.source_lambda`). The most musically consequential knob.
   Lower ⇒ finer sources (kick and snare split, rows fill with drums);
   higher ⇒ coarser (bass and guitar merge). Worth tuning against real
   material; the right value depends on how much timbre variety a song has.
3. **Descriptor weights** (default timbre 1.0 · envelope 0.5 · metrical
   0.3). Timbre dominates identity. Raising the metrical weight separates
   same-timbre sources that play different rhythmic roles, but too high
   splits one instrument that changes pattern between song sections.
4. **Row brightness semantics** (default: activation + rising-edge flash).
   Brightness = the cluster's summed live NMF activation (per-row AGC), and
   a rising edge triggers a short full-brightness flash so percussive rows
   read as hits rather than flutter. Alternative: pure activation (calmer,
   less punchy).
5. **Cold start** (default: rows live immediately from the seeded
   dictionary). W is seeded with generic shapes (low-frequency bumps,
   harmonic combs, broadband noise), so the first seconds show coarse
   "register" rows that sharpen into instruments as W and the clusters
   adapt (~10–30 s). Alternative: hide rows behind a band-bar fallback
   until clusters mature — cleaner, but shows nothing interesting during
   the most attention-grabbing first seconds.

## Consequences

- SignalGrid rows become *discovered* sources: drums flash on one row,
  sustained instruments hold on others, with no instrument-type rules.
- Row identity is only as stable as the cluster matching; expect some
  reshuffling on dramatic song-structure changes.
- The NMF dictionary adapts per song (~30 s memory): the display "learns"
  each track and re-learns on track changes.
- CPU: ~0.1–0.3 ms per 5.8 ms hop on the Mac (two small FFTs + 40×10
  multiplicative updates); comfortably within a Pi 5 core alongside
  rendering. Removing the pitch tracker (~1.3 ms/chunk) more than pays for
  the 4× hop rate.
- Polyphonic identity comes from the factorization, not a pitch tracker —
  the old monophonic "dominant voice" limitation is gone, replaced by the
  milder limitation of K=10 components and timbre/pitch conflation in the
  40-band representation.
