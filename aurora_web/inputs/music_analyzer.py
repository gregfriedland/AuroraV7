"""Real-time music analysis: beat tracking + unsupervised source discovery.

ADR 0004 (beat tracking) + ADR 0005 (ML source discovery). The pipeline per
1024-sample capture chunk:

- SourceDiscovery splits the chunk into 4 hops of 256 samples (5.8 ms) and
  runs a dual-resolution spectral frontend (2048-sample window below 500 Hz,
  512 above), online KL-NMF (v ~= W h), and periodic DP-means clustering of
  the NMF components into instrument sources.
- A kick-band onset detector (inside the frontend) feeds the predictive
  bar-locked beat oscillator (tempo evidence + downbeat accents).

Hand-engineered extractors from earlier revisions (snare/hat onsets,
K-weighted loudness, monophonic pitch, vibrato/ADSR heuristics) were removed
per ADR 0005 — the learned model supersedes them.
"""

import time
from dataclasses import dataclass

import numpy as np

try:
    import aubio
    HAVE_AUBIO = True
except Exception:  # pragma: no cover - import guard
    aubio = None
    HAVE_AUBIO = False


@dataclass
class MusicFeatures:
    """Feature snapshot passed to drawers."""

    timestamp: float = 0.0

    # Levels / texture
    volume: float = 0.0              # raw RMS 0-1
    bands: np.ndarray | None = None  # 16-band fold of the ML frontend (0-1)
    bass: float = 0.0
    mids: float = 0.0
    highs: float = 0.0

    # Kick onsets (beat-tracker evidence; also usable by drawers)
    onset_kick: bool = False
    kick_strength: float = 0.0

    # Beat / bar (predictive, bar-locked)
    bpm: float | None = None
    beat_phase: float = 0.0
    beat_now: bool = False
    bar_phase: float = 0.0
    beat_in_bar: int = 1
    downbeat_now: bool = False

    # Discovered sources (ADR 0005)
    sources: np.ndarray | None = None          # activation 0-1 per slot
    source_centroid: np.ndarray | None = None  # x position 0-1 per slot
    source_active: tuple = ()                  # rising edge per slot
    source_hit_time: np.ndarray | None = None  # latched last-hit wall time per slot

    # ---- Backward compatibility with the old AudioInput ----
    @property
    def spectrum(self) -> np.ndarray | None:
        return self.bands

    @property
    def beat_onset(self) -> bool:
        return self.beat_now


class SourceDiscovery:
    """Dual-resolution frontend + online NMF + component clustering.

    See ADR 0005. All state updates are incremental; cost is ~0.1-0.3 ms
    per 5.8 ms hop in numpy.
    """

    HOP = 256
    WIN_LOW = 2048
    WIN_HIGH = 512
    SPLIT_HZ = 500.0
    F = 40                  # bands
    K = 20                  # NMF components
    NMF_ITERS = 6
    SPARSITY = 0.06         # L1-ish penalty in the h update
    W_SWEEP_EVERY = 32      # hops (~0.19 s)
    REFRESH_HOPS = 86       # cluster refresh (~0.5 s)
    HIST_HOPS = 1376        # ~8 s of activation history: common-fate
                            # correlation needs several events per source
                            # even when each plays 1-2 slots per 2 s bar
    WHITEN_DECAY = 0.9996   # per hop (~10 s half-life at 172 hops/s)
    STAT_GAMMA = 0.9998     # sufficient-statistics forgetting (~30 s)
    MET_GAMMA = 0.9995      # metrical histogram forgetting
    VOLUME_GATE = 0.005     # freeze learning below this RMS

    # Kick onset detection (beat-tracker evidence)
    KICK_MAX_HZ = 130.0
    KICK_FLOOR = 0.15
    KICK_THRESH = 1.5
    KICK_MIN_IOI = 0.09

    # Descriptor block weights (ADR 0005 knob 3): common-fate correlation
    # dominates identity; timbre breaks ties between rhythm-locked sources
    W_CORR = 1.0
    W_TIMBRE = 0.3
    W_MET = 0.3

    def __init__(self, sample_rate: int = 44100, n_slots: int = 5,
                 dp_lambda: float = 0.35):
        self.sample_rate = sample_rate
        self.n_slots = n_slots
        self.dp_lambda = dp_lambda
        self.hop_dt = self.HOP / sample_rate

        # --- frontend ---
        self._ring = np.zeros(self.WIN_LOW, dtype=np.float32)
        self._pending = np.zeros(0, dtype=np.float32)
        self._win_low = np.hanning(self.WIN_LOW)
        self._win_high = np.hanning(self.WIN_HIGH)
        freqs_low = np.fft.rfftfreq(self.WIN_LOW, 1.0 / sample_rate)
        freqs_high = np.fft.rfftfreq(self.WIN_HIGH, 1.0 / sample_rate)
        edges = np.logspace(np.log10(40), np.log10(16000), self.F + 1)
        # Band folding as two matrices (vectorized: bands = M_lo@mag_lo + M_hi@mag_hi)
        self._band_center = np.sqrt(edges[:-1] * edges[1:])
        self._fold_low = np.zeros((self.F, len(freqs_low)))
        self._fold_high = np.zeros((self.F, len(freqs_high)))
        for i in range(self.F):
            lo, hi = edges[i], edges[i + 1]
            use_low = self._band_center[i] < self.SPLIT_HZ
            freqs = freqs_low if use_low else freqs_high
            idx = np.where((freqs >= lo) & (freqs < hi))[0]
            if len(idx) == 0:
                idx = np.array([min(np.searchsorted(freqs, lo), len(freqs) - 1)])
            target = self._fold_low if use_low else self._fold_high
            target[i, idx] = 1.0 / len(idx)
        self._kick_bands = np.where(self._band_center <= self.KICK_MAX_HZ)[0]

        # whitening state
        self._peak = np.full(self.F, 1e-6)
        self._global_max = 1e-6
        self._prev_white = np.zeros(self.F)
        self.frame = np.zeros(self.F, dtype=np.float32)  # latest whitened v

        # --- kick onset state ---
        self._kick_hist: list[float] = []
        self._last_kick = 0.0

        # --- NMF ---
        self.W = self._seed_dictionary()
        self.h = np.full(self.K, 0.1)
        self._A = np.eye(self.K) * 1e-3
        self._B = self.W * 1e-3
        self._hop_count = 0
        self._learn_hops = 0   # annealing clock (only advances while learning)

        # --- descriptors ---
        self._h_hist = np.zeros((self.HIST_HOPS, self.K), dtype=np.float32)
        self._met_hist = np.zeros((self.K, 16), dtype=np.float32)

        # --- clusters / slots ---
        self._clusters: list[dict] = []   # {id, centroid, members, activity}
        self._next_id = 0
        self._slots: list[dict | None] = []   # display slots (sticky by id)
        self._slot_ids: list[int | None] = [None] * n_slots
        self._slot_last_cx: dict[int, float] = {}  # slot index -> last centroid
        self._slot_agc: dict[int, float] = {}
        self._prev_act: dict[int, float] = {}
        self._slot_hit_time: dict[int, float] = {}  # cluster id -> last hit

    # ------------------------------------------------------------------
    # Dictionary seeding (ADR 0005: low bumps, harmonic combs, noise)
    # ------------------------------------------------------------------
    def _seed_dictionary(self) -> np.ndarray:
        """Build K seed templates from an ordered pool of generic shapes."""
        rng = np.random.default_rng(7)
        x = np.arange(self.F)
        octave = self.F / np.log2(16000 / 40)  # bands per octave (~4.6)

        def bump(center, width=2.0):
            return np.exp(-0.5 * ((x - center) / width) ** 2)

        def comb(base, n_harm=5):
            out = np.zeros(self.F)
            for n in range(1, n_harm + 1):
                out += bump(base + octave * np.log2(n), 1.0) / n
            return out

        pool = [
            bump(2.0), bump(5.0), bump(8.0),                # low thumps
            comb(10.0), comb(14.0), comb(18.0), comb(22.0),  # combs, low->mid
            np.linspace(0.2, 1.0, self.F),                  # bright tilt
            np.concatenate([np.zeros(self.F - 12), np.ones(12)]),  # hats
            np.ones(self.F) * 0.5,                          # flat
            comb(12.0), comb(16.0), comb(20.0), comb(24.0),
            bump(16.0, 4.0), bump(28.0, 4.0),               # broad bumps
            comb(26.0), comb(28.0), comb(30.0), comb(32.0),
            bump(12.0, 3.0), bump(22.0, 3.0), bump(34.0, 3.0),
        ]
        W = np.stack(pool[: self.K], axis=1) if self.K <= len(pool) else \
            np.stack(pool + [bump(rng.uniform(2, 38), 2.0)
                             for _ in range(self.K - len(pool))], axis=1)
        W = W + rng.uniform(0.0, 0.02, W.shape)             # break symmetry
        return W / np.linalg.norm(W, axis=0, keepdims=True)

    # ------------------------------------------------------------------
    # Per-chunk processing
    # ------------------------------------------------------------------
    def process_chunk(self, chunk: np.ndarray, t_end: float, slot16: int,
                      volume: float) -> list[tuple[float, float, bool, float]]:
        """Run all complete hops in `chunk`.

        Returns kick events: [(hop_time, kick_odf, fired, strength), ...]
        """
        samples = np.concatenate([self._pending, chunk.astype(np.float32)])
        n_hops = len(samples) // self.HOP
        self._pending = samples[n_hops * self.HOP:]
        events = []
        for i in range(n_hops):
            hop = samples[i * self.HOP:(i + 1) * self.HOP]
            t_hop = t_end - (n_hops - 1 - i) * self.hop_dt
            events.append(self._process_hop(hop, t_hop, slot16, volume))
        return events

    def _process_hop(self, hop: np.ndarray, t_hop: float, slot16: int,
                     volume: float) -> tuple[float, float, bool, float]:
        self._ring = np.roll(self._ring, -self.HOP)
        self._ring[-self.HOP:] = hop

        mag_low = np.abs(np.fft.rfft(self._ring * self._win_low))
        mag_high = np.abs(np.fft.rfft(self._ring[-self.WIN_HIGH:] * self._win_high))
        raw = np.log1p(self._fold_low @ mag_low + self._fold_high @ mag_high)

        # adaptive whitening (floor vs global max kills phantom flux)
        self._global_max = max(float(raw.max()), self._global_max * self.WHITEN_DECAY, 1e-6)
        floor = 0.01 * self._global_max
        self._peak = np.maximum.reduce([raw, self._peak * self.WHITEN_DECAY,
                                        np.full(self.F, floor)])
        v = (raw / self._peak).astype(np.float32)
        flux = np.maximum(0.0, v - self._prev_white)
        self._prev_white = v
        self.frame = v

        # --- kick onset (beat evidence) ---
        kick_odf = float(np.mean(flux[self._kick_bands]))
        mean = float(np.mean(self._kick_hist)) if self._kick_hist else 0.0
        self._kick_hist.append(kick_odf)
        if len(self._kick_hist) > self.HIST_HOPS:
            self._kick_hist.pop(0)
        fired = (
            kick_odf > max(self.KICK_FLOOR, mean * self.KICK_THRESH)
            and (t_hop - self._last_kick) > self.KICK_MIN_IOI
        )
        strength = 0.0
        if fired:
            self._last_kick = t_hop
            strength = float(np.clip((kick_odf - self.KICK_FLOOR) / (3 * self.KICK_FLOOR), 0, 1))

        # --- NMF: solve h (always), learn W (when not silent) ---
        # PARTIAL warm start: pure warm-starting locks the solver onto
        # whichever explanation won the previous hit, so identical hits get
        # explained by alternating component sets (bistability) and the same
        # drum flickers between display rows; pure cold-starting loses the
        # sustain context that separates held notes from hits. Blending
        # toward neutral keeps continuity without the lock-in.
        h = 0.6 * self.h + 0.4 * 0.1
        for _ in range(self.NMF_ITERS):
            wh = self.W @ h + 1e-9
            # +SPARSITY in the denominator (sparse NMF): discourages
            # components from smearing across sources — a component shared
            # between two instruments correlates with both and chains their
            # clusters together
            h = h * (self.W.T @ (v / wh)) / (self.W.T.sum(axis=1) + self.SPARSITY)
        self.h = np.maximum(h, 1e-6)

        if volume > self.VOLUME_GATE:
            self._A = self.STAT_GAMMA * self._A + np.outer(self.h, self.h)
            self._B = self.STAT_GAMMA * self._B + np.outer(v, self.h)
            if self._hop_count % self.W_SWEEP_EVERY == 0:
                W_new = self.W * (self._B + 1e-9) / (self.W @ self._A + 1e-9)
                norms = np.linalg.norm(W_new, axis=0, keepdims=True)
                W_new = W_new / np.maximum(norms, 1e-9)
                # Semi-adaptive bases (Dittmar & Gartner): anneal dictionary
                # learning. Full adaptation for the first ~15 s, then settle —
                # endless drift reshuffles component roles under a stationary
                # signal, destabilizing cluster identity and display rows.
                self._learn_hops += self.W_SWEEP_EVERY
                alpha = max(0.05, float(np.exp(-self._learn_hops / (172.0 * 15))))
                self.W = (1 - alpha) * self.W + alpha * W_new
                norms = np.linalg.norm(self.W, axis=0, keepdims=True)
                self.W = self.W / np.maximum(norms, 1e-9)

        # --- descriptor state ---
        self._h_hist = np.roll(self._h_hist, -1, axis=0)
        self._h_hist[-1] = self.h
        self._met_hist *= self.MET_GAMMA
        self._met_hist[:, slot16 % 16] += self.h

        self._hop_count += 1
        if self._hop_count % self.REFRESH_HOPS == 0:
            self._refresh_clusters()

        return (t_hop, kick_odf, fired, strength)

    # ------------------------------------------------------------------
    # Clustering (DP-means over component descriptors, ADR 0005)
    # ------------------------------------------------------------------
    def _descriptors(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (descriptors (K, D), activity (K,)).

        Identity is dominated by COMMON FATE: each component's descriptor is
        primarily its correlation profile against all other components'
        activation envelopes. All frequency strata of one physical source
        (kick thump + kick click) co-activate hit after hit, so their
        profiles are nearly identical and they cluster together immediately
        — regardless of how different their spectra are. Timbre is demoted
        to a tie-breaker for sources playing locked rhythms.
        """
        hist = self._h_hist
        mean = hist.mean(axis=0)
        env = self._event_envelopes(hist)
        hc = env - env.mean(axis=0)
        std = hc.std(axis=0)
        T = env.shape[0]
        corr = (hc.T @ hc) / (T * np.outer(std, std) + 1e-9)
        # components with no envelope evidence get a self-only profile so
        # they never merge on noise
        silent = std < 1e-5
        corr[silent, :] = 0.0
        corr[:, silent] = 0.0
        np.fill_diagonal(corr, 1.0)

        met = self._met_hist / (self._met_hist.sum(axis=1, keepdims=True) + 1e-9)
        timbre = self.W / np.maximum(np.linalg.norm(self.W, axis=0, keepdims=True), 1e-9)
        desc = np.concatenate([
            self.W_CORR * corr,                         # (K, K) common fate
            self.W_TIMBRE * timbre.T,                   # (K, F) tie-breaker
            self.W_MET * met * 4.0,                     # x4: unit-sum hist is tiny
        ], axis=1)
        desc = desc / np.maximum(np.linalg.norm(desc, axis=1, keepdims=True), 1e-9)
        return desc, mean

    MERGE_CORR = 0.45       # cluster-envelope correlation that forces a merge

    @staticmethod
    def _event_envelopes(hist: np.ndarray) -> np.ndarray:
        """Event-timescale envelopes for common-fate correlation.

        The ~100 ms max-filter absorbs NMF explaining-away, where
        same-source components trade energy hop-to-hop.
        """
        from scipy.ndimage import maximum_filter1d
        return maximum_filter1d(hist, size=17, axis=0, mode="nearest")

    def _merge_correlated_clusters(self, clusters: list[dict]) -> list[dict]:
        if len(clusters) < 2:
            return clusters
        smoothed = self._event_envelopes(self._h_hist)
        env = np.stack([smoothed[:, cl["members"]].sum(axis=1) for cl in clusters])
        env = env - env.mean(axis=1, keepdims=True)
        norms = np.linalg.norm(env, axis=1)
        valid = norms > 1e-4
        env = env / np.maximum(norms, 1e-9)[:, None]
        corr = env @ env.T

        merged = [False] * len(clusters)
        order = sorted(range(len(clusters)), key=lambda i: -clusters[i]["weight"])
        for a_i in order:
            if merged[a_i]:
                continue
            for b_i in order:
                if b_i == a_i or merged[b_i]:
                    continue
                if valid[a_i] and valid[b_i] and corr[a_i, b_i] > self.MERGE_CORR:
                    a, b = clusters[a_i], clusters[b_i]
                    a["members"].extend(b["members"])
                    w = a["weight"] + b["weight"]
                    a["centroid"] = (a["centroid"] * a["weight"]
                                     + b["centroid"] * b["weight"]) / w
                    a["centroid"] /= max(np.linalg.norm(a["centroid"]), 1e-9)
                    a["weight"] = w
                    merged[b_i] = True
        return [cl for i, cl in enumerate(clusters) if not merged[i]]

    CORR_JOIN = 0.55        # min direct leader correlation to join a cluster

    def _refresh_clusters(self) -> None:
        desc, activity = self._descriptors()
        order = np.argsort(-activity)

        # event-scale envelope correlation between components (for the
        # leader test below)
        env = self._event_envelopes(self._h_hist)
        hc = env - env.mean(axis=0)
        std = hc.std(axis=0)
        ccorr = (hc.T @ hc) / (env.shape[0] * np.outer(std, std) + 1e-9)

        # LEADER clustering: a component joins a cluster only if it
        # correlates strongly with the cluster's LEADER (its most active
        # member) DIRECTLY. Components shared between two instruments
        # correlate moderately with both; centroid methods (DP-means)
        # let them chain the instruments into one cluster.
        new: list[dict] = []
        for k in order:
            best, best_score = None, 0.0
            for cl in new:
                leader = cl["members"][0]
                c = float(ccorr[k, leader]) if std[k] > 1e-5 and std[leader] > 1e-5 else 0.0
                score = c + 0.15 * float(desc[k] @ desc[leader])
                if score > best_score:
                    best, best_score = cl, score
            if best is not None and best_score >= self.CORR_JOIN:
                best["members"].append(int(k))
                best["weight"] += activity[k] + 1e-9
                w = best["weight"]
                best["centroid"] = (best["centroid"] * (w - activity[k] - 1e-9)
                                    + desc[k] * (activity[k] + 1e-9)) / w
                best["centroid"] /= max(np.linalg.norm(best["centroid"]), 1e-9)
            else:
                new.append({"centroid": desc[k].copy(), "weight": activity[k] + 1e-9,
                            "members": [int(k)]})

        # Cluster-level common-fate merge: if two clusters' summed envelopes
        # (event-scale, max-filtered — see _descriptors) still correlate
        # strongly, they are strata of one source that the descriptor
        # clustering failed to bind. Guarantees one-source-one-row.
        new = self._merge_correlated_clusters(new)

        # Identity continuity by MEMBER OVERLAP: component indices are
        # stable across refreshes while descriptor centroids drift as the
        # dictionary learns. Centroid-similarity matching spawned spurious
        # "new" clusters that hopped between display slots (visible jitter).
        prev = list(self._clusters)
        for cl in sorted(new, key=lambda c: -c["weight"]):
            best, best_ov = None, 0.0
            cm = set(cl["members"])
            for p in prev:
                pm = set(p["members"])
                ov = len(cm & pm) / max(len(cm | pm), 1)
                if ov > best_ov:
                    best, best_ov = p, ov
            if best is not None and best_ov >= 0.3:
                cl["id"] = best["id"]
                prev = [p for p in prev if p is not best]
            else:
                cl["id"] = self._next_id
                self._next_id += 1

        for cl in new:
            cl["activity"] = float(sum(activity[m] for m in cl["members"]))
            spec = np.zeros(self.F)
            for m in cl["members"]:
                spec += self.W[:, m] * (activity[m] + 1e-9)
            total = spec.sum()
            cl["centroid_x"] = float((np.arange(self.F) @ spec) / (total * (self.F - 1))) \
                if total > 1e-9 else 0.5
        self._clusters = new

        # Sticky slot assignment: a cluster id keeps its display slot for as
        # long as it stays in the top-N. Re-sorting every refresh made rows
        # reshuffle whenever clusters appeared/vanished, destroying the
        # visual correlation between a row and "its" instrument.
        top = sorted(new, key=lambda c: -c["activity"])[: self.n_slots]
        top_ids = {c["id"] for c in top}
        by_id = {c["id"]: c for c in top}
        if not any(cid in top_ids for cid in self._slot_ids):
            # initial assignment (or full turnover): order by frequency
            ordered = sorted(top, key=lambda c: c["centroid_x"])
            self._slot_ids = [c["id"] for c in ordered] + \
                             [None] * (self.n_slots - len(ordered))
        else:
            # remember where each slot's occupant sat in frequency before
            # clearing, so replacements can land in the same place
            for i, cid in enumerate(self._slot_ids):
                if cid is not None and cid in by_id:
                    self._slot_last_cx[i] = by_id[cid]["centroid_x"]
            # keep survivors in place; clear vacated slots
            self._slot_ids = [cid if cid in top_ids else None
                              for cid in self._slot_ids]
            # place new clusters in free slots, preferring the slot whose
            # previous occupant was spectrally closest — when a cluster's id
            # churns (membership reshuffle), its successor lands on the SAME
            # row instead of hopping
            new_cls = [c for c in top if c["id"] not in self._slot_ids]
            free = [i for i, cid in enumerate(self._slot_ids) if cid is None]
            for cl in sorted(new_cls, key=lambda c: -c["activity"]):
                if not free:
                    break
                best = min(free, key=lambda i: abs(
                    self._slot_last_cx.get(i, 0.5) - cl["centroid_x"]))
                self._slot_ids[best] = cl["id"]
                free.remove(best)
        self._slots = [by_id.get(cid) for cid in self._slot_ids]

    # ------------------------------------------------------------------
    # Display snapshot
    # ------------------------------------------------------------------
    HIT_THR = 0.35          # gated activation that registers a hit
    HIT_REFRACTORY = 0.12   # s between hits per slot

    def snapshot(self, silent: bool = False, now: float = 0.0,
                 ) -> tuple[np.ndarray | None, np.ndarray | None, tuple, np.ndarray | None]:
        """Return (sources, centroids, active, hit_times) for this chunk.

        hit_times LATCHES the wall-clock time of each slot's most recent
        hit (activation crossing HIT_THR). The render loop samples the
        latest snapshot asynchronously, and under load chunks process in
        bursts — short activation pulses get overwritten before any render
        frame sees them. A timestamp latch cannot be missed.

        With `silent` (input below the volume gate) all activations are
        forced to zero and AGC/peak references are frozen — otherwise the
        references decay toward the noise floor during silence and ambient
        noise eventually flashes the channels.
        """
        if not any(cl is not None for cl in self._slots):
            return None, None, (), None
        n = self.n_slots
        sources = np.zeros(n, dtype=np.float32)
        centroids = np.ones(n, dtype=np.float32)
        hit_times = np.zeros(n, dtype=np.float64)
        for i in range(n):
            cl = self._slots[i] if i < len(self._slots) else None
            if cl is not None:
                hit_times[i] = self._slot_hit_time.get(cl["id"], 0.0)
        active = []
        if silent:
            for i in range(n):
                cl = self._slots[i] if i < len(self._slots) else None
                centroids[i] = cl["centroid_x"] if cl is not None else 1.0
                if cl is not None:
                    self._prev_act[cl["id"]] = 0.0
                active.append(False)
            return sources, centroids, tuple(active), hit_times
        # raw activation per occupied slot (for relative gating)
        raw = np.zeros(n)
        for i in range(n):
            cl = self._slots[i] if i < len(self._slots) else None
            if cl is not None:
                raw[i] = float(sum(self.h[m] for m in cl["members"]))
        total = float(raw.sum())
        # absolute reference: decaying peak of total activation. Between
        # hits the noise-floor cluster holds ~100% of a TINY total, so a
        # purely relative gate lights it up; gating against the recent peak
        # keeps near-silence dark.
        self._act_peak = max(total, getattr(self, "_act_peak", 1e-3) * 0.999)
        for i in range(n):
            cl = self._slots[i] if i < len(self._slots) else None
            if cl is None:
                active.append(False)
                continue
            cid = cl["id"]
            # faster AGC (~half-life 8 s at 43 snapshots/s) keeps pulse
            # heights near full scale despite dictionary drift
            agc = max(raw[i], self._slot_agc.get(cid, 1e-3) * 0.998)
            self._slot_agc[cid] = agc
            a = float(np.clip(raw[i] / max(agc, 1e-6), 0.0, 1.0))
            # relative-strength gate: only sources carrying a real share of
            # the current music light up
            rel = raw[i] / max(total, 1e-9)
            a *= float(np.clip(3.0 * rel, 0.0, 1.0))
            # absolute gate vs the recent activation peak
            a *= float(np.clip(raw[i] / (0.15 * self._act_peak), 0.0, 1.0))
            rising = a > self._prev_act.get(cid, 0.0) + 0.25
            self._prev_act[cid] = a
            sources[i] = a
            centroids[i] = cl["centroid_x"]
            active.append(bool(rising))
            # latch hit timestamps at chunk rate (see docstring)
            if a > self.HIT_THR and \
                    now - self._slot_hit_time.get(cid, 0.0) > self.HIT_REFRACTORY:
                self._slot_hit_time[cid] = now
                hit_times[i] = now
        return sources, centroids, tuple(active), hit_times


class PredictiveBeatOscillator:
    """Phase-locked oscillator that schedules beats ahead of time.

    A backend supplies (bpm, detected beat timestamps). The oscillator keeps
    its own clock-based schedule; corrections accumulate during the bar and
    apply only at bar boundaries, so beats stay metronome-steady within a
    measure.
    """

    # Corrections apply once per BAR (not per detection), so the gains are
    # higher than a per-detection PLL would use
    SLEW = 0.6              # fraction of median phase error corrected per bar
    MAX_STEP = 0.15         # max fraction of a period corrected at once
    BPM_BLEND = 0.15

    def __init__(self, latency_s: float = 0.06):
        self.latency_s = latency_s
        self.bpm: float | None = None
        self._next_beat: float | None = None
        self._beat_index = 0          # 0-3
        self._downbeat_offset = 0
        # accent histogram for the downbeat heuristic
        self._accents = np.zeros(4)
        self._pending_bpm: float | None = None
        self._pending_errs: list[float] = []

    @property
    def period(self) -> float | None:
        return 60.0 / self.bpm if self.bpm else None

    def on_detection(self, t: float, bpm: float | None) -> None:
        """Register a detected beat at capture time t (latency compensated)."""
        t -= self.latency_s
        if self.bpm is None:
            if bpm and bpm > 0:
                self.bpm = bpm
                self._pending_bpm = bpm
                self._next_beat = t + self.period
            return
        if bpm and bpm > 0:
            target = self._pending_bpm if self._pending_bpm is not None else self.bpm
            self._pending_bpm = target + self.BPM_BLEND * (bpm - target)
        period = self.period
        err = t - self._next_beat
        err -= round(err / period) * period
        self._pending_errs.append(err)

    def _apply_bar_correction(self) -> None:
        period = self.period
        if self._pending_bpm is not None:
            self.bpm = self._pending_bpm
        if self._pending_errs:
            err = float(np.median(self._pending_errs))
            step = float(np.clip(err * self.SLEW,
                                 -self.MAX_STEP * period, self.MAX_STEP * period))
            self._next_beat += step
            self._pending_errs = []

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
        beat_now = False
        while now >= self._next_beat:
            beat_now = True
            self._beat_index = (self._beat_index + 1) % 4
            if (self._beat_index - self._downbeat_offset) % 4 == 0:
                self._apply_bar_correction()
            self._next_beat += self.period
        phase = float(np.clip(1.0 - (self._next_beat - now) / self.period, 0.0, 1.0))
        beat_in_bar = (self._beat_index - self._downbeat_offset) % 4 + 1
        downbeat = beat_now and beat_in_bar == 1
        return beat_now, phase, beat_in_bar, downbeat


class _AubioTempoBackend:
    """Beat detection via aubio.tempo."""

    def __init__(self, sample_rate: int, hop_size: int):
        self._tempo = aubio.tempo("default", hop_size * 4, hop_size, sample_rate)

    def process(self, chunk: np.ndarray, now: float) -> tuple[float | None, float | None]:
        """Return (bpm, detection_time or None) for this chunk."""
        is_beat = self._tempo(chunk.astype(np.float32))
        bpm = float(self._tempo.get_bpm()) or None
        if bpm and not (40 <= bpm <= 220):
            bpm = None
        return bpm, (now if is_beat[0] else None)


class _InternalTempoBackend:
    """Pure-numpy fallback: autocorrelation of the kick onset envelope."""

    BUF_S = 6.0

    def __init__(self, sample_rate: int, hop_size: int):
        self._hop_dt = hop_size / sample_rate
        self._env: list[float] = []
        self._maxlen = int(self.BUF_S / self._hop_dt)
        self._count = 0
        self._bpm: float | None = None
        self._bpm_history: list[float] = []

    def add_onset_strength(self, odf: float) -> None:
        self._env.append(odf)
        if len(self._env) > self._maxlen:
            self._env.pop(0)

    def process(self, kick_fired: bool, now: float) -> tuple[float | None, float | None]:
        self._count += 1
        # recompute tempo every ~0.5 s of envelope samples
        if self._count % max(1, int(0.5 / self._hop_dt)) == 0 \
                and len(self._env) >= self._maxlen // 2:
            env = np.array(self._env) - np.mean(self._env)
            ac = np.correlate(env, env, mode="full")[len(env) - 1:]
            lag_min = max(1, int(0.25 / self._hop_dt))   # 240 BPM
            lag_max = min(len(ac) - 1, int(1.0 / self._hop_dt))  # 60 BPM
            if lag_max > lag_min and ac[0] > 0:
                lags = np.arange(lag_min, lag_max)
                # mild preference for ~120 BPM
                prior = np.exp(-0.5 * ((60.0 / (lags * self._hop_dt) - 120) / 80) ** 2)
                best = int(lags[int(np.argmax(ac[lag_min:lag_max] * prior))])
                # parabolic interpolation for sub-hop lag precision
                lag = float(best)
                if 1 <= best < len(ac) - 1:
                    a, b_, c_ = ac[best - 1], ac[best], ac[best + 1]
                    denom = a - 2 * b_ + c_
                    if abs(denom) > 1e-12:
                        lag = best + float(np.clip(0.5 * (a - c_) / denom, -0.5, 0.5))
                # median over recent estimates damps oscillation between
                # adjacent autocorrelation peaks
                self._bpm_history.append(60.0 / (lag * self._hop_dt))
                if len(self._bpm_history) > 9:
                    self._bpm_history.pop(0)
                self._bpm = float(np.median(self._bpm_history))
        return self._bpm, (now if kick_fired else None)


class MusicAnalyzer:
    """Full analysis pipeline: PCM chunks in, MusicFeatures out."""

    def __init__(self, sample_rate: int = 44100, hop_size: int = 1024,
                 beat_tracker: str = "internal", latency_ms: float = 60.0,
                 n_sources: int = 5, source_lambda: float = 0.35,
                 clock=time.time):
        self.sample_rate = sample_rate
        self.hop_size = hop_size
        self._clock = clock

        self.discovery = SourceDiscovery(sample_rate, n_slots=n_sources,
                                         dp_lambda=source_lambda)
        self.oscillator = PredictiveBeatOscillator(latency_s=latency_ms / 1000.0)

        self.backend_name = beat_tracker
        self._aubio_backend = None
        self._internal_backend = _InternalTempoBackend(sample_rate, SourceDiscovery.HOP)
        if beat_tracker in ("aubio", "beatnet") and HAVE_AUBIO:
            try:
                self._aubio_backend = _AubioTempoBackend(sample_rate, hop_size)
            except Exception:
                self._aubio_backend = None
        # BeatNet detections are injected externally via inject_beat();
        # once any arrive, the local backend is suppressed
        self._external_beat: tuple[float, float | None, bool] | None = None
        self._external_active = False

        self._kick_times: list[float] = []
        self._bands16_split = None
        self.features = MusicFeatures()

    def inject_beat(self, t: float, bpm: float | None, is_downbeat: bool) -> None:
        """External tracker (BeatNet subprocess) reports a beat."""
        self._external_beat = (t, bpm, is_downbeat)
        self._external_active = True

    def _fix_tempo_octave(self) -> None:
        """Correct half-tempo octave errors using the kick-onset rate."""
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
        """Analyze one capture chunk of mono float32 samples in [-1, 1]."""
        now = self._clock()
        f = MusicFeatures(timestamp=now)
        f.volume = float(np.sqrt(np.mean(chunk ** 2)))

        # 16th-note slot from the PREVIOUS frame's bar state (≤23 ms stale)
        slot16 = int(self.features.bar_phase * 16) % 16

        # --- source discovery (4 hops) + kick events ---
        events = self.discovery.process_chunk(chunk, now, slot16, f.volume)
        kick_fired = False
        kick_strength = 0.0
        kick_time = now
        for t_hop, odf, fired, strength in events:
            self._internal_backend.add_onset_strength(odf)
            if fired:
                kick_fired = True
                kick_strength = max(kick_strength, strength)
                kick_time = t_hop
        f.onset_kick = kick_fired
        f.kick_strength = kick_strength

        # --- beat tracking -> predictive oscillator ---
        bpm = detection = None
        if self._external_beat is not None:
            t, ext_bpm, is_down = self._external_beat
            self._external_beat = None
            bpm, detection = ext_bpm, t
            if is_down:
                self.oscillator._downbeat_offset = (self.oscillator._beat_index + 1) % 4
        elif self._external_active:
            pass  # external tracker owns beat detection
        elif self._aubio_backend is not None:
            bpm, detection = self._aubio_backend.process(chunk, now)
        else:
            bpm, detection = self._internal_backend.process(kick_fired, kick_time)
        if detection is not None:
            self.oscillator.on_detection(detection, bpm)
        if kick_fired:
            self.oscillator.on_kick(kick_strength)
            self._kick_times.append(kick_time)
            if len(self._kick_times) > 12:
                self._kick_times.pop(0)
            self._fix_tempo_octave()
        f.beat_now, f.beat_phase, f.beat_in_bar, f.downbeat_now = self.oscillator.tick(now)
        f.bpm = self.oscillator.bpm
        f.bar_phase = ((f.beat_in_bar - 1) + f.beat_phase) / 4.0

        # --- texture back-compat: fold the 40 whitened bands to 16 ---
        if self._bands16_split is None:
            self._bands16_split = np.array_split(np.arange(SourceDiscovery.F), 16)
        v = self.discovery.frame
        f.bands = np.array([float(np.mean(v[idx])) for idx in self._bands16_split],
                           dtype=np.float32)
        f.bass = float(np.mean(f.bands[:3]))
        f.mids = float(np.mean(f.bands[3:10]))
        f.highs = float(np.mean(f.bands[10:]))

        # --- discovered sources ---
        f.sources, f.source_centroid, f.source_active, f.source_hit_time = \
            self.discovery.snapshot(
                silent=f.volume < SourceDiscovery.VOLUME_GATE, now=now)

        self.features = f
        return f
