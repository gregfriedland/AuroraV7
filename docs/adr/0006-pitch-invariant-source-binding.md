# ADR 0006: Pitch-Invariant Source Binding for Melodic Instruments

**Status:** Accepted (binding shipped behind conservative gates; full
consolidation blocked on bar-tracking robustness — see Gaps)
**Date:** 2026-06-11

## Context

ADR 0005's source discovery binds NMF components into instrument clusters
by **common fate** (envelope correlation), with metrical-slot agreement and
raw-timbre cosine as minor terms. That works for percussion and slowly
changing pitched material, but a **dense pitch-changing sustained
instrument** (blow/voice at ~1 note/s) lit 2–4 SignalGrid channels
simultaneously and never consolidated:

- Each note excites different NMF components (a template is tied to one
  pitch).
- Components of *different* notes are **anti-correlated** — note A sounding
  means note B isn't — so common fate actively pushes a melody's notes
  apart.
- The battery solo test missed this because its sustained pattern is
  sparser (1 note per 2 s bar); at 1 note/s the per-note clusters each
  carry enough energy to claim a display row.

Offline repro: `blow`/`voice` events (random f0 per note) every 1.0 s for
45 s through the battery render harness, measuring per-row lit coverage
and simultaneous-row count. Baseline: 2.4–2.7 rows lit during notes,
best-row coverage 0.6–0.9 spread across rows, never consolidating.

## Decision

Bind a melody's notes with a **transposition-invariant timbre signature**,
applied only under gates that carry the cross-instrument discrimination,
plus upstream fixes to the metrical evidence the gates depend on.

1. **Invariant signature** (`_inv_timbre`) — `|FFT|` of the mean-centered
   NMF template along the log-spaced band axis. A pitch change translates
   the harmonic pattern along log-frequency; the FFT magnitude is
   unchanged. Mean-centering kills the DC bin (otherwise all positive
   templates look alike).
2. **Join-level bonus** — in the leader-clustering score, `+0.5 × invsim`
   when metrical profiles agree near-perfectly (`msim > 0.95`) with real
   metrical evidence on both sides. 0.95 is data-driven: with correct
   tempo, melody-note pairs measure msim median 0.96, while
   cross-instrument confusions during tempo settling peak at 0.949.
3. **Cluster-level gated merge** — per-note clusters merge when leaders'
   invariant timbres match (`> 0.80`) and metrical profiles agree, in two
   regimes (`metsim > 0.92` on timbre alone; `0.85–0.92` additionally
   requires cluster-envelope corr `< 0.05` — co-playing instruments
   measure +0.11..+0.28, alternating melody halves −0.10..−0.66), with
   both leaders **episodic** (10th-percentile/max envelope < 0.25) so the
   never-quiet noise-floor cluster — spectrally identical to cymbal under
   the invariant signature — is excluded.
4. **Broadband tempo evidence** — the internal tempo backend now
   autocorrelates **full-spectrum** flux instead of kick-band flux (kick
   detection/downbeat accents unchanged). Voice (f0 ≥ 160 Hz) and blow
   (≥ 330 Hz) leave nothing in the kick band, so tempo was garbage
   (77–218 BPM for a metronomic 1 note/s pattern) and every metrical
   profile downstream smeared toward uniform — where all profiles
   cosine-match and metrical gating is blind. With broadband evidence the
   dense repro converges to the true 60 BPM and drum+strum to 120.
5. **Metrical hygiene** — slot histograms only accumulate after the beat
   tracker locks (`slot16 = -1` before); pre-lock everything piled into
   slot 0 and all profiles came out identical, which let the ungated-era
   binding glue kick+ping. While a component has no real evidence the
   *base* metrical term scores neutral (1.0, the de-facto prior behavior)
   so early clusters don't fragment, but the invariant-timbre paths
   require real evidence on both sides. Cluster metrical profiles use the
   **leader's** histogram only — summing members lets shared components
   blur the profile toward all-slots (a kick cluster metsim'd 0.92+
   against the ping cluster and absorbed it).

## Results (shipped configuration)

- All 58 audio-scope tests pass (e2e syncopation, music analyzer incl.
  kick/bass and drum/strum hard cases, audio feed, signal grid).
- Solo battery: clean across repeated runs (baseline-level; the gates'
  false-lighting regressions found during development are fixed).
- Duo/trio battery: within baseline's run-to-run variance (this session:
  duo pass, trio 1/5 vs gate 2/5; baseline measured duo fail and trio 1/5
  in the same session — the provisional gates are red at HEAD too).
- Dense repro: **modest** improvement — best-row coverage 0.68–1.0
  (baseline 0.6–0.9), mean rows lit 1.7–2.4 (baseline 2.4–2.7). Identity
  usually consolidates to one dominant row but extra rows still flash.

**Demonstrated ceiling:** with the merge gates relaxed (no eventfulness
veto, MET_MERGE alone), the repro reached full consolidation — best row
1.00 in 6/6 runs, multi-row lighting 9–52% transient-only — but that
configuration falsely merged the noise floor into cymbal solo (false-lit
35%) and, under smeared profiles, kick+strum. The machinery works; its
*evidence* (bar tracking) is what limits it. See Gaps.

## Tried and reverted (kept so they aren't re-tried blind)

- **Ungated invariant blending** (weight 0.35 in the join score): any two
  single-blob spectra match under shift invariance — merged kick+ping,
  e2e fell 30/30 → 11/30.
- **Bounded-shift template matching** (max centered correlation over band
  shifts ≤ ~1 octave) as a sharper, register-aware replacement for
  `|FFT|`: real instruments are not pure translations. Voice keeps formant
  and breath-noise strata fixed while only the fundamental region moves;
  true note pairs scored near zero (e.g. 0.69 vs |FFT|'s 0.94, often
  negative). The loose `|FFT|` signature also binds a source's
  non-translating strata, which is load-bearing.
- **Anti-correlation veto at component level** ("alternating envelopes =
  two instruments"): a sustained instrument's formant stratum co-occurs
  with every note, so within-instrument pairs are often positively
  correlated; and melody halves are *strongly* anti-correlated (−0.66).
  The sign is only usable as the cluster-level positive-corr ceiling
  (decision 3).
- **Participation-ratio (profile concentration) cap**: under a bad tempo
  estimate smear hits *everyone* equally (PR 13–15 in both the solo
  melody and the duo), so the cap blocks legitimate and bogus merges
  alike.
- **Spectral structuredness gate** (high-quefrency energy share) to
  exclude noise-like templates from timbre binding: measured per-component
  values overlap completely (cymbal 0.30–0.67 vs voice 0.14–0.70) —
  learned templates are messy mixtures, not archetypes.
- **Median-duty / summed-envelope eventfulness**: a dense melody cluster
  is high-duty by definition, and its envelope-sum never goes quiet
  because it legitimately contains the always-on formant stratum. Only
  the low-percentile leader test (decision 3) survived; even it engages
  conservatively.

## Gaps / next task

1. **Bar-tracking robustness is THE blocker.** Tempo now locks on melodic
   material, but (a) it takes 10–25 s, (b) it octave-flips on long-decay
   material (cymbal solo: 179→123→62→61→121 over 30 s — each flip remaps
   slots and re-smears every profile; `_fix_tempo_octave` is kick-IOI
   based and never engages), and (c) beat **phase** corrections come only
   from kick onsets, so without percussion the bar dead-reckons
   (60.4 vs 60.0 BPM ⇒ ~1 slot drift / 9 s) and profiles stay soft.
   Fix direction: octave disambiguation + phase corrections from
   broadband onset detections. Once profiles are sharp and stable, the
   demonstrated-ceiling merge configuration should be re-enabled
   (relax/remove the eventfulness veto, revisit MET_MERGE regimes).
2. **Cymbal/noise timbre degeneracy.** Filtered noise is invariant-timbre
   identical to the noise floor (cinvsim 0.98); only behavioral evidence
   separates them. Today that's the eventfulness veto; a sharper notion
   (e.g. event-locked vs free-running activation) would allow looser
   metrical gates.
3. **Duo/trio battery gates remain provisional and red at baseline**
   (hard pairs kick/bass, snare/guitar, blow/voice; ADR 0005). Blow+voice
   duos are the pair most exposed to gap 1 (neither feeds phase
   corrections).
4. **Settling window**: consolidation evidence needs ~10–20 s from cold
   start; transient extra-row flashes during that window are inherent to
   evidence-gated binding.
5. **Pi deployment is several commits behind** (was unreachable at last
   sync).

## Notes

- Debug hook: set `SourceDiscovery._debug_inv = []` to log decisive
  invariant-timbre joins and gated cluster merges
  (`("join"|"merge", hop, …, msim, invsim, corr)`).
- The dense repro lives at `aurora_web/tests/dense_solo_repro.py`
  (diagnostic script, not a pytest gate). Promote it into the battery as
  a deterministic dense-solo test once gap 1 lands.

## Next direction: bounded-shift matching, done per-stratum

The most promising refinement of the timbre signature is to revisit
**bounded-shift template matching** — max centered correlation between two
templates over log-band shifts limited to a plausible melodic range
(~±1 octave ≈ ±5 bands). Its appeal is exactly what `|FFT|` magnitude
throws away: *register*. Unbounded invariance makes a 60 Hz kick thump and
a 4 kHz ping literally identical (both single blobs), forcing all the
cross-instrument discrimination onto fragile metrical gates; a
shift-bounded matcher refuses that pairing natively (they can never align
within the bound) while still matching true transpositions at the shift
equal to their interval, which would let the metrical gates relax and
reduce the dependence on bar-tracking quality (gap 1). The naive version
failed because a whole template is not a pure translation — voice moves
its fundamental region while formant and breath-noise strata stay fixed —
so the fix is to stop treating the template as one rigid shape: split it
into strata (e.g. contiguous spectral regions, or a learned
moving/stationary decomposition) and score a pair as "same instrument" when
the *moving* strata match under a small shift AND the *stationary* strata
match at zero shift. That composite keeps register awareness, models how
real instruments actually transpose, and degrades gracefully to today's
behavior for percussive single-blob sources. Prototype against the dense
repro plus the kick/ping, kick/bass, and cymbal/noise hard pairs before
wiring it into the gates.
