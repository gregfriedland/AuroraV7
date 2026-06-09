# ADR 0001: Onset Detection with 16th-Note Quantization

**Status:** Implemented  
**Date:** 2026-04-12

## Context

The BeatTracker detects spectral flux onsets but only uses them to nudge the phase oscillator -- individual note events are discarded. Drawers have no access to per-note data for visualization (e.g., rhythm patterns, attack shapes, spectral fingerprints).

## Decision

Add an `OnsetTracker` class alongside `BeatTracker` that captures each onset as a discrete event, quantizes it to a 16th-note grid (16 positions per bar), and records its spectral fingerprint and amplitude envelope.

### Data Model

**Onset** dataclass with: position (0-15), strength, 16-band spectrum snapshot, volume envelope (up to 8 frames), age, and phase error from exact grid point.

**Quantization:** Phase 0-4 maps to 16th notes via `round(phase * 4.0) % 16`. Each beat has 4 subdivisions.

### Key Design Decisions

- **Separate class from BeatTracker** -- BeatTracker handles tempo/phase, OnsetTracker handles note-level events. Clean separation of concerns.
- **Reuse existing 16 bands** for spectral signature -- already computed, matches display resolution.
- **Single-value envelope** (RMS volume, not per-band) -- 16x less data for marginal display benefit on a 32x18 matrix.
- **8-frame envelope** (~370ms at 21.5 Hz) -- covers percussive transients without overlapping next onset in fast music.
- **Two-bar buffer** (current + previous) -- sufficient for real-time visualization, keeps AudioInput lean.
- **Deduplicate by position** -- one onset per 16th-note slot per bar, strongest wins on collision.
- **onset_grid convenience property** -- compact float32[16] for drawers that just want a pattern grid.

## Implementation

### Files Modified

- `aurora_web/inputs/audio_feed.py` -- Added `Onset` dataclass, `OnsetTracker` class (~80 lines), exposed `is_onset`/`onset_strength` from BeatTracker, added onset fields to `AudioInput`, wired into `AudioFeed._analyze()` and `MockAudioFeed`
- `aurora_web/inputs/__init__.py` -- Export `Onset`
- `aurora_web/drawers/audio_viz.py` -- Replaced bass/mids/highs row with onset grid display; later redesigned to beat circle + onset grid
- `aurora_web/core/drawer_manager.py` -- Added `_on_drawer_change` callback for lazy resource management
- `aurora_web/main.py` -- Lazy video feed start/stop (only when Camera drawer active), Mac audio source auto-detection, configurable audio source

### Additional Changes (same session)

- **Default drawer changed** from AudioViz to AlienBlob (works without audio input)
- **Video feed made lazy** -- only starts when Camera drawer is selected, reducing idle CPU from ~77% to ~3%
- **Mac audio capture** -- added `mac:` source type using ffmpeg + avfoundation + BlackHole loopback
- **Hardware diagnostics** -- added `tools/led_test.py` standalone serial test and `HARDWARE.md` documentation

## Consequences

- Drawers now have rich per-note data (onset position, strength, spectrum, envelope) for rhythm visualization
- OnsetTracker adds negligible CPU overhead (runs at analysis FPS ~21.5 Hz, simple arithmetic)
- AudioInput grows by 3 fields but they're None when no audio is active
