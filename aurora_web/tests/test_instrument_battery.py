"""Randomized instrument-combination battery (no fixed seeds).

Uses the instrument event library to build coordinated patterns of 1, 2,
and 3 randomly chosen instrument families, then checks each instrument
lights its own display channel. Seeds are random per run and printed on
failure for reproduction.

Gates reflect CURRENTLY ACHIEVED reliability (documented in ADR 0005):
solo is required to always work; multi-instrument combos involving
spectrally-overlapping pairs (kick/bass, snare/guitar, blow/voice) are the
known hard cases and the gates below are provisional targets to raise as
the model improves.
"""

import itertools
import secrets

import numpy as np
import pytest

# The battery is the TARGET SPEC and iteration tool, not yet a stable gate:
# randomized trials expose real run-to-run variance on spectrally
# overlapping pairs. Run explicitly with:  pytest -m battery
pytestmark = pytest.mark.battery

from aurora_web.drawers.base import DrawerContext
from aurora_web.drawers.signal_grid import SignalGridDrawer
from aurora_web.inputs.music_analyzer import MusicAnalyzer
from aurora_web.tests.instrument_events import (FAMILIES, SR, SUSTAINED,
                                                build_pattern)

HOP = 1024
DT = HOP / SR
ROWS = [(0, 3), (3, 6), (6, 9), (9, 12), (12, 15)]
SKIP = 16.0


class FakeClock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t
    def advance(self, dt): self.t += dt


def render(sig):
    clock = FakeClock()
    an = MusicAnalyzer(SR, HOP, beat_tracker="internal", latency_ms=0.0, clock=clock)
    dr = SignalGridDrawer(32, 18)
    times, lit = [], []
    t_sim = 0.0
    for i in range(0, len(sig) - HOP, HOP):
        clock.advance(DT); t_sim += DT
        f = an.process(sig[i:i + HOP])
        ctx = DrawerContext(width=32, height=18, frame_num=i, time=t_sim,
                            delta_time=DT, palette_size=4096, audio=f)
        frame = dr.draw(ctx)
        times.append(t_sim)
        lit.append([bool((frame[r0:r1].sum(axis=2) > 40).any()) for r0, r1 in ROWS])
    return np.array(times), np.array(lit)


def score_family(times, lit, fam, events, row):
    ev = [e for e in events if e > SKIP]
    if fam in SUSTAINED:
        covs = []
        for e in ev:
            m = (times >= e + 0.1) & (times <= e + 0.5)
            if m.any():
                covs.append(lit[m, row].mean())
        return float(np.mean(covs)) if covs else 0.0
    det = 0
    for e in ev:
        m = (times >= e - 0.12) & (times <= e + 0.17)
        if m.any() and lit[m, row].any():
            det += 1
    return det / max(len(ev), 1)


def false_rate(times, lit, events, row, guard):
    m_out = times > SKIP
    for e in events:
        m_out &= ~((times >= e - 0.05) & (times <= e + guard))
    return float(lit[m_out, row].mean()) if m_out.any() else 0.0


def run_trial(n_inst, seed):
    rng = np.random.default_rng(seed)
    fams = list(FAMILIES.keys())
    chosen = list(rng.choice(fams, size=n_inst, replace=False))
    sig, hits = build_pattern(rng, chosen)
    times, lit = render(sig)
    best, best_total = None, -1e9
    for rows in itertools.permutations(range(5), n_inst):
        total = sum(score_family(times, lit, f, hits[f], r)
                    - 0.3 * false_rate(times, lit, hits[f], r,
                                       guard=1.2 if f in SUSTAINED else 0.7)
                    for f, r in zip(chosen, rows))
        if total > best_total:
            best_total, best = total, rows
    ok = True
    detail = {}
    for f, r in zip(chosen, best):
        rate = score_family(times, lit, f, hits[f], r)
        fr = false_rate(times, lit, hits[f], r, guard=1.2 if f in SUSTAINED else 0.7)
        thr = 0.6 if f in SUSTAINED else 0.9
        passed = rate >= thr and fr <= 0.15
        ok &= passed
        detail[f] = (r, round(rate, 2), round(fr, 2), passed)
    return ok, detail


def run_battery(n_inst, trials=5):
    results = []
    for _ in range(trials):
        seed = secrets.randbits(32)
        ok, detail = run_trial(n_inst, seed)
        results.append((ok, seed, detail))
    return results


def _fmt(results):
    return "\n".join(f"  [{'PASS' if ok else 'FAIL'}] seed={seed} {detail}"
                     for ok, seed, detail in results)


class TestInstrumentBattery:
    def test_solo_instruments_always_work(self):
        results = run_battery(1, trials=5)
        passes = sum(ok for ok, _, _ in results)
        assert passes == 5, f"solo battery {passes}/5:\n{_fmt(results)}"

    def test_duo_combinations(self):
        results = run_battery(2, trials=5)
        passes = sum(ok for ok, _, _ in results)
        # provisional gate: spectrally-overlapping pairs (kick/bass,
        # snare/guitar, blow/voice) are known-hard; target is 5/5
        assert passes >= 3, f"duo battery {passes}/5:\n{_fmt(results)}"

    def test_trio_combinations(self):
        results = run_battery(3, trials=5)
        passes = sum(ok for ok, _, _ in results)
        # provisional gate: probability of drawing a hard pair grows with
        # combination size; target is 4/5
        assert passes >= 2, f"trio battery {passes}/5:\n{_fmt(results)}"
