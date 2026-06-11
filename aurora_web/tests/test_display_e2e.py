"""End-to-end display regression: audio in, rendered frames out (ADR 0005).

Stringent criteria on a syncopated two-instrument beat (low kick on the
beat, high ping on the off-beat): every hit must flash its own fixed row,
nothing may light outside hit windows, all other rows stay dark.
"""

import numpy as np
from scipy import signal as sps

from aurora_web.drawers.base import DrawerContext
from aurora_web.drawers.signal_grid import SignalGridDrawer
from aurora_web.inputs.music_analyzer import MusicAnalyzer

SR = 44100
HOP = 1024
DT = HOP / SR
ROWS = [(0, 3), (3, 6), (6, 9), (9, 12), (12, 15)]


def syncopation(dur=40.0, seed=5):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    sig = np.zeros(n)
    kicks, pings = [], []
    t = 0.5
    while t < dur - 0.2:
        i0 = int(t * SR); L = int(0.12 * SR); tt = np.arange(L) / SR
        freq = 45 + 50 * np.exp(-tt * 30)
        body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-tt * 18)
        click = rng.standard_normal(L) * np.exp(-tt * 200) * 0.3
        s = sig[i0:i0 + L]; s += (rng.uniform(0.8, 1.0) * (body + click))[:len(s)]
        kicks.append(t); t += 1.0
    sos = sps.butter(6, 3000 / (SR / 2), "highpass", output="sos")
    t = 1.25
    while t < dur - 0.2:
        i0 = int(t * SR); L = int(0.06 * SR); tt = np.arange(L) / SR
        burst = rng.standard_normal(L) * np.exp(-tt * 80)
        ping = np.sin(2 * np.pi * 4200 * tt) * np.exp(-tt * 60)
        seg = sps.sosfilt(sos, burst * 0.5 + ping * 0.5)
        s = sig[i0:i0 + L]; s += (rng.uniform(0.7, 0.95) * seg)[:len(s)]
        pings.append(t); t += 1.0
    sig += rng.standard_normal(n) * 0.005
    return (sig / np.abs(sig).max() * 0.8).astype(np.float32), kicks, pings


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


def test_syncopated_two_instruments_clean_display():
    SKIP = 10.0
    sig, kicks, pings = syncopation()
    times, lit = render(sig)
    sel = times > SKIP

    def hit_rate(hits, row, win=0.12):
        det = tot = 0
        for h in hits:
            if h < SKIP: continue
            tot += 1
            m = (times >= h - win) & (times <= h + win + 0.05)
            if m.any() and lit[m, row].any(): det += 1
        return det, tot

    def false_rate(hits, row, guard=0.45):
        m_out = sel.copy()
        for h in hits:
            m_out &= ~((times >= h - 0.05) & (times <= h + guard))
        return float(lit[m_out, row].mean()) if m_out.any() else 0.0

    kr = [hit_rate(kicks, r) for r in range(5)]
    pr = [hit_rate(pings, r) for r in range(5)]
    best, best_score = None, -1e9
    for ki in range(5):
        for pi_ in range(5):
            if ki == pi_: continue
            kd, kt = kr[ki]; pd, pt = pr[pi_]
            score = kd / max(kt, 1) + pd / max(pt, 1) \
                - 0.5 * (false_rate(kicks, ki) + false_rate(pings, pi_))
            if score > best_score:
                best_score, best = score, (ki, pi_)
    krow, prow = best
    kd, kt = kr[krow]; pd, pt = pr[prow]
    k_false = false_rate(kicks, krow)
    p_false = false_rate(pings, prow)
    other = max(float(lit[sel][:, r].mean())
                for r in range(5) if r not in (krow, prow))

    assert kd / kt >= 0.95, f"kick {kd}/{kt} on row {krow}"
    assert pd / pt >= 0.90, f"ping {pd}/{pt} on row {prow}"
    assert k_false <= 0.10, f"kick row false-lit {k_false:.0%}"
    assert p_false <= 0.10, f"ping row false-lit {p_false:.0%}"
    assert other <= 0.05, f"uninvolved rows lit {other:.0%}"
