"""Offline repro: dense pitch-changing sustained instrument (blow/voice).

One note every 1.0 s for 45 s — denser than the battery's 1-note-per-2s-bar
pattern. Measures per-row coverage during note windows and how many display
rows light simultaneously. Healthy behavior: one dominant row, ~0 extra rows.

Diagnostic script, not a pytest gate (ADR 0006: full consolidation is
blocked on bar-tracking robustness). Run:

    .venv/bin/python -m aurora_web.tests.dense_solo_repro
"""

import numpy as np

from aurora_web.tests.instrument_events import FAMILIES, SR
from aurora_web.tests.test_instrument_battery import (SKIP, render,
                                                      score_family,
                                                      false_rate)

DUR = 45.0
PERIOD = 1.0


def build_dense(rng, fam):
    n = int(DUR * SR)
    sig = np.zeros(n)
    gen = FAMILIES[fam][0]
    times = []
    t = 1.0
    while t < DUR - 1.5:
        te = t + rng.uniform(-0.008, 0.008)
        ev = gen(rng)
        i0 = int(te * SR)
        seg = sig[i0:i0 + len(ev)]
        seg += ev[:len(seg)]
        times.append(te)
        t += PERIOD
    sig += rng.standard_normal(n) * 0.004
    peak = np.abs(sig).max()
    return (sig / max(peak, 1e-9) * 0.8).astype(np.float32), times


def main(seeds=(11, 22, 33)):
    overall_fail = False
    for fam in ("blow", "voice"):
        for seed in seeds:
            rng = np.random.default_rng(seed)
            sig, events = build_dense(rng, fam)
            times, lit = render(sig)
            ev = [e for e in events if e > SKIP]

            # coverage per row inside note windows
            cov = [score_family(times, lit, fam, events, r) for r in range(5)]
            best_row = int(np.argmax(cov))
            fr = false_rate(times, lit, events, best_row, guard=1.2)

            # simultaneity: mean #rows lit during note windows
            in_win = np.zeros(len(times), dtype=bool)
            for e in ev:
                in_win |= (times >= e + 0.1) & (times <= e + 0.5)
            n_lit = lit[in_win].sum(axis=1)
            mean_rows = float(n_lit[n_lit > 0].mean()) if (n_lit > 0).any() else 0.0
            multi_frac = float((n_lit >= 2).mean())

            ok = cov[best_row] >= 0.6 and fr <= 0.15 and multi_frac <= 0.10
            overall_fail |= not ok
            print(f"{fam:5s} seed={seed:3d} cov={['%.2f' % c for c in cov]} "
                  f"best=row{best_row} ({cov[best_row]:.2f}) fr={fr:.2f} "
                  f"mean_rows_lit={mean_rows:.2f} multi2+={multi_frac:.2f} "
                  f"{'PASS' if ok else 'FAIL'}")
    print("OVERALL:", "FAIL" if overall_fail else "PASS")


if __name__ == "__main__":
    main()
