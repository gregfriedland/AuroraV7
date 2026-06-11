"""Synthetic instrument-event library for display regression tests.

Each generator renders ONE event into a float32 buffer and returns it.
Events are deliberately realistic-ish: amplitude/pitch jitter, noisy
attacks, inharmonicity — nothing is a clean sine.

Families (used when sampling combinations; variants within a family share
timbre and are never asked to occupy separate display channels):

    drum_lo   - kick: pitch-swept low thump + click
    drum_hi   - snare: mid tone burst + broadband noise
    cymbal    - bright long-decay filtered noise
    guitar    - plucked note or strummed chord (mid register)
    bass      - plucked note or two-note chord (low register)
    blow      - harmonica/trumpet-like sustained note with vibrato
    voice     - sung vowel: harmonics shaped by formant resonances
"""

import numpy as np
from scipy import signal as sps

SR = 44100


def _ramp(n, attack_s, release_s):
    env = np.ones(n)
    a = max(1, int(attack_s * SR))
    r = max(1, int(release_s * SR))
    env[:a] *= np.linspace(0, 1, a)
    env[-r:] *= np.linspace(1, 0, r)
    return env


def drum_lo(rng):
    """Kick: 95->45 Hz sweep + click, ~0.12 s."""
    L = int(0.12 * SR)
    tt = np.arange(L) / SR
    freq = 45 + 50 * np.exp(-tt * 30)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-tt * 18)
    click = rng.standard_normal(L) * np.exp(-tt * 200) * 0.35
    return ((body + click) * rng.uniform(0.8, 1.0)).astype(np.float32)


def drum_hi(rng):
    """Snare: ~200 Hz tone burst + broadband noise, ~0.18 s."""
    L = int(0.18 * SR)
    tt = np.arange(L) / SR
    tone = np.sin(2 * np.pi * rng.uniform(180, 220) * tt) * np.exp(-tt * 25) * 0.5
    noise = rng.standard_normal(L) * np.exp(-tt * 22)
    sos = sps.butter(2, [400 / (SR / 2), 8000 / (SR / 2)], "bandpass", output="sos")
    noise = sps.sosfilt(sos, noise)
    return ((tone + noise * 0.8) * rng.uniform(0.75, 1.0)).astype(np.float32)


def cymbal(rng):
    """Bright metallic noise, long decay, ~0.8 s."""
    L = int(0.8 * SR)
    tt = np.arange(L) / SR
    noise = rng.standard_normal(L)
    sos = sps.butter(4, 5500 / (SR / 2), "highpass", output="sos")
    noise = sps.sosfilt(sos, noise)
    # a few metallic partials
    for f in rng.uniform(6000, 12000, 4):
        noise += 0.15 * np.sin(2 * np.pi * f * tt)
    return (noise * np.exp(-tt * 5.0) * rng.uniform(0.5, 0.8) * 0.5).astype(np.float32)


def _pluck(rng, f0, dur, n_harm=8, decay_base=1.2, bright=0.8):
    L = int(dur * SR)
    tt = np.arange(L) / SR
    f = f0 * rng.uniform(0.998, 1.002)
    out = np.zeros(L)
    for h in range(1, n_harm + 1):
        inharm = 1 + 0.0003 * h * h
        out += (bright / h ** 0.9) * np.sin(2 * np.pi * f * h * inharm * tt) \
            * np.exp(-tt * (decay_base + 0.8 * h))
    pick = rng.standard_normal(L) * np.exp(-tt * 300) * 0.12
    return ((out + pick) * rng.uniform(0.8, 1.0)).astype(np.float32)


GUITAR_NOTES = [196.0, 246.9, 293.7, 329.6, 392.0]
BASS_NOTES = [41.2, 55.0, 61.7, 82.4, 98.0]


def guitar_note(rng):
    return _pluck(rng, rng.choice(GUITAR_NOTES), 0.6) * 0.6


def guitar_chord(rng):
    root = rng.choice(GUITAR_NOTES[:3])
    L = int(0.7 * SR)
    out = np.zeros(L)
    for s, ratio in enumerate((1.0, 1.26, 1.5, 2.0)):  # major-ish voicing
        st = int(s * 0.008 * SR)
        seg = _pluck(rng, root * ratio, 0.7 - s * 0.008)
        out[st:st + len(seg)] += seg
    return (out * 0.35).astype(np.float32)


def bass_note(rng):
    return _pluck(rng, rng.choice(BASS_NOTES), 0.5, n_harm=5, decay_base=2.0) * 0.9


def bass_chord(rng):
    root = rng.choice(BASS_NOTES[:3])
    a = _pluck(rng, root, 0.5, n_harm=5, decay_base=2.0)
    b = _pluck(rng, root * 1.5, 0.5, n_harm=5, decay_base=2.0)
    return ((a + b) * 0.5).astype(np.float32)


def blow(rng, dur=None):
    """Harmonica/trumpet: sustained rich harmonics, slow attack, vibrato."""
    dur = dur or rng.uniform(0.6, 0.9)
    L = int(dur * SR)
    tt = np.arange(L) / SR
    f0 = rng.uniform(330, 550)
    vib = 1 + 0.02 * np.sin(2 * np.pi * rng.uniform(4.5, 6.5) * tt) * np.minimum(tt / 0.3, 1)
    phase = 2 * np.pi * np.cumsum(f0 * vib) / SR
    out = np.zeros(L)
    for h, amp in enumerate((1.0, 0.7, 0.55, 0.35, 0.25, 0.15), start=1):
        out += amp * np.sin(phase * h)
    breath = rng.standard_normal(L) * 0.02
    env = _ramp(L, 0.05, 0.08)
    return ((out + breath) * env * rng.uniform(0.35, 0.5) * 0.5).astype(np.float32)


def voice(rng, dur=None):
    """Sung vowel: glottal-ish harmonics through two formant resonances."""
    dur = dur or rng.uniform(0.6, 0.9)
    L = int(dur * SR)
    tt = np.arange(L) / SR
    f0 = rng.uniform(160, 260)
    vib = 1 + 0.015 * np.sin(2 * np.pi * rng.uniform(4.5, 6.0) * tt) * np.minimum(tt / 0.25, 1)
    phase = 2 * np.pi * np.cumsum(f0 * vib) / SR
    src = np.zeros(L)
    for h in range(1, 14):
        src += np.sin(phase * h) / h ** 0.5
    # vowel formants (e.g. "ah": ~800 Hz and ~1200 Hz)
    out = np.zeros(L)
    for fc, bw, g in ((rng.uniform(700, 900), 130, 1.0), (rng.uniform(1100, 1400), 180, 0.6)):
        sos = sps.butter(2, [(fc - bw) / (SR / 2), (fc + bw) / (SR / 2)],
                         "bandpass", output="sos")
        out += g * sps.sosfilt(sos, src)
    env = _ramp(L, 0.06, 0.1)
    return (out * env * rng.uniform(0.5, 0.7) * 0.6).astype(np.float32)


# family name -> list of event generators
FAMILIES = {
    "drum_lo": [drum_lo],
    "drum_hi": [drum_hi],
    "cymbal": [cymbal],
    "guitar": [guitar_note, guitar_chord],
    "bass": [bass_note, bass_chord],
    "blow": [blow],
    "voice": [voice],
}

# is the family percussive (flash) or sustained (hold)?
SUSTAINED = {"blow", "voice"}


def build_pattern(rng, families, dur=35.0, bar_s=2.0):
    """Coordinated multi-instrument pattern on a shared 16th-note grid.

    Each instrument gets 1-2 fixed slots per bar (distinct across
    instruments), repeated every bar with timing jitter.

    Returns (signal, {family: [event_times]}).
    """
    n = int(dur * SR)
    sig = np.zeros(n)
    slot_s = bar_s / 8.0  # 8th-note grid within the bar
    available = list(range(8))
    rng.shuffle(available)
    hits = {}
    for fam in families:
        n_slots = 1 if fam in SUSTAINED else int(rng.integers(1, 3))
        slots = [available.pop() for _ in range(n_slots)]
        gen = FAMILIES[fam][int(rng.integers(len(FAMILIES[fam])))]
        times = []
        t = bar_s
        while t < dur - 1.5:
            for s in slots:
                te = t + s * slot_s + rng.uniform(-0.008, 0.008)
                ev = gen(rng)
                i0 = int(te * SR)
                seg = sig[i0:i0 + len(ev)]
                seg += ev[:len(seg)]
                times.append(te)
            t += bar_s
        hits[fam] = times
    sig += rng.standard_normal(n) * 0.004
    peak = np.abs(sig).max()
    return (sig / max(peak, 1e-9) * 0.8).astype(np.float32), hits
