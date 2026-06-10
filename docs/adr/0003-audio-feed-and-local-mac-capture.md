# ADR 0003: Audio Feed and Local Mac Capture

**Status:** Accepted / Implemented (mac: and pipe: sources landed 2026-06-09)  
**Date:** 2026-06-09

## Context

Aurora needs audio-reactive data for drawers while supporting two different development loops:

- **Production on Raspberry Pi** -- audio arrives from AirPlay or Linux capture and drives the physical LED wall.
- **Local development on Mac** -- music should play on the Mac and feed the same analysis path so drawers can be tuned in the browser simulator before deploying to the Pi.

The codebase currently has two related mechanisms:

- `aurora_web/inputs/audio_feed.py` captures PCM audio through external commands, analyzes it in-process, and exposes an `AudioInput` snapshot to drawers.
- `aurora_web/core/find_beats.py` provides `ExternalBeatFeed`, a compatibility layer for AuroraV6-style `findBeatsCmd` commands that emit onset lines like `[01001]`.

## Decision

Keep audio capture command-driven and explicit. `AudioFeed` owns PCM capture and analysis; `ExternalBeatFeed` owns compatibility with external onset detectors. Both are process boundaries around tools that can be swapped per platform without coupling drawers to OS-specific audio APIs.

For local Mac development, use a virtual loopback audio device:

1. Install `BlackHole 2ch`.
2. Create a macOS Multi-Output Device that sends system audio to both speakers/headphones and `BlackHole 2ch`.
3. Capture `BlackHole 2ch` with `ffmpeg` using AVFoundation.
4. Feed the resulting raw mono `s16le` PCM stream into Aurora's audio analysis path.

Expected Mac capture command shape:

```bash
ffmpeg -f avfoundation -i ":BlackHole 2ch" -f s16le -ar 44100 -ac 1 -
```

Device-index form is also valid after listing devices:

```bash
ffmpeg -f avfoundation -list_devices true -i ""
ffmpeg -f avfoundation -i ":0" -f s16le -ar 44100 -ac 1 -
```

On Raspberry Pi, keep Linux capture options:

- `pulse` -> `parec --format=s16le --rate=<sample_rate> --channels=1`
- `alsa:<device>` -> `arecord -D <device> -f S16_LE -r <sample_rate> -c 1 -t raw`
- AirPlay pipe, when enabled, should be represented as a raw PCM FIFO source such as `pipe:/tmp/shairport-audio`

## Audio Model

`AudioFeed` reads fixed-size PCM chunks, converts them to float samples in `[-1, 1]`, and computes:

- RMS `volume`
- 16-band normalized FFT `spectrum`
- derived `bass`, `mids`, and `highs`
- `beat_onset`
- `beat_phase`
- estimated `bpm`

Drawers should consume `AudioInput` rather than reading capture processes directly. This keeps visualization code independent from AirPlay, ALSA, PulseAudio, AVFoundation, and test-file playback.

## Local Simulator

Local iteration should not require physical LEDs. The web app should broadcast server-rendered pattern frames back to browser clients so the existing canvas can act as a simulator display.

In the current branch, pattern preview frames are broadcast over the WebSocket as binary RGB frames every few render frames. The frontend draws them into the preview canvas. This makes Mac audio testing practical once the audio source is live.

## Mac Verification

BlackHole is available when `ffmpeg` lists it under AVFoundation audio devices:

```text
AVFoundation audio devices:
[0] BlackHole 2ch
```

Capture is working when a short volume test reports non-silent levels while music is playing and routed through the Multi-Output Device:

```bash
ffmpeg -hide_banner -f avfoundation -i ":0" -t 2 -af volumedetect -f null -
```

A result near `-90 dB` means capture opened successfully but is receiving silence. That usually means either no music is playing or macOS output is not routed to the Multi-Output Device that includes BlackHole.

## Current Implementation Gaps

- The current `AudioFeed` implementation supports `pulse`, `alsa:<device>`, and `file:<path>`.
- `mac:<device>` and `pipe:<path>` source parsing should be added to `AudioFeed._build_capture_command()`.
- macOS capture should default to one channel because the ffmpeg command outputs mono with `-ac 1`.
- Log messages should avoid AirPlay-specific wording for non-pipe sources.
- `AudioFeed.stop()` should tolerate capture processes that have already exited.
- Configuration should expose the audio source, for example:

```yaml
inputs:
  audio:
    enabled: true
    source: "mac:BlackHole 2ch"
    channels: 1
```

## Consequences

- Local drawer iteration becomes faster because Mac playback can drive the same visualizer path without deploying to the Pi.
- Platform-specific audio setup stays outside drawer code.
- BlackHole setup is an external prerequisite on Mac; without correct macOS output routing, the capture process can run but deliver silence.
- The simulator preview adds low-bandwidth WebSocket traffic, but the frame size is small (`32 * 18 * 3` bytes), so it is acceptable for local and control-browser use.
