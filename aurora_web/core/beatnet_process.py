"""Optional BeatNet beat/downbeat tracking in a separate process (ADR 0004).

BeatNet (PyTorch CRNN + particle filter) is the only packaged real-time
joint beat+downbeat tracker. The heavy imports (torch, madmom) happen only
inside the subprocess; if they fail, the manager reports unavailability and
the MusicAnalyzer falls back to its aubio/internal backend.

Audio flows in as 44.1 kHz mono float32 chunks; BeatNet works at 22.05 kHz
with hop 512, so each 1024-sample chunk is decimated by 2.
"""

import multiprocessing as mp
import queue as queue_mod
import time

import numpy as np


def _beatnet_loop(in_queue: mp.Queue, out_queue: mp.Queue, stop_event,
                  sample_rate: int) -> None:
    """Subprocess main loop. Heavy imports stay in here."""
    try:
        # numpy 2.x compat shims for BeatNet's particle filter
        if not hasattr(np, "in1d"):
            np.in1d = np.isin
        if not hasattr(np, "float"):
            np.float = float
        from BeatNet.BeatNet import BeatNet  # noqa: lazy heavy import
        estimator = BeatNet(1, mode="realtime", inference_model="PF",
                            plot=[], thread=False)
    except Exception as e:  # pragma: no cover - depends on optional install
        out_queue.put(("error", f"BeatNet unavailable: {e}"))
        return

    out_queue.put(("ready", None))
    stream_t0 = None        # wall-clock time of stream sample 0
    samples_seen = 0        # in 22.05 kHz samples
    last_beat_stream_t = -1.0

    while not stop_event.is_set():
        try:
            chunk = in_queue.get(timeout=0.5)
        except queue_mod.Empty:
            continue
        if chunk is None:
            break

        now = time.time()
        chunk22 = chunk[::2].astype(np.float32)  # 44.1k -> 22.05k
        if stream_t0 is None:
            stream_t0 = now
        samples_seen += len(chunk22)
        # keep stream clock anchored to wall clock (drift correction)
        stream_t0 = now - samples_seen / 22050.0

        try:
            output = estimator.process(chunk22)
        except Exception as e:  # pragma: no cover
            out_queue.put(("error", f"BeatNet process failed: {e}"))
            return

        if output is None or len(output) == 0:
            continue
        for row in np.atleast_2d(np.asarray(output)):
            beat_t, beat_class = float(row[0]), int(row[1])
            if beat_t <= last_beat_stream_t:
                continue
            last_beat_stream_t = beat_t
            wall_t = stream_t0 + beat_t
            is_downbeat = beat_class == 1  # BeatNet: 1 = downbeat, 2 = beat
            try:
                out_queue.put_nowait(("beat", (wall_t, is_downbeat)))
            except queue_mod.Full:
                pass


class BeatNetManager:
    """Parent-side handle for the BeatNet subprocess."""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.available = False
        self._failed = False
        self._in: mp.Queue | None = None
        self._out: mp.Queue | None = None
        self._stop = None
        self._process: mp.Process | None = None

    def start(self) -> None:
        ctx = mp.get_context("spawn")
        self._in = ctx.Queue(maxsize=64)
        self._out = ctx.Queue(maxsize=64)
        self._stop = ctx.Event()
        self._process = ctx.Process(
            target=_beatnet_loop,
            args=(self._in, self._out, self._stop, self.sample_rate),
            daemon=True,
        )
        self._process.start()
        print("[BeatNet] Subprocess starting (model load may take a while)...")

    def feed(self, chunk: np.ndarray) -> None:
        """Send one PCM chunk; drops frames if the tracker can't keep up."""
        if self._failed or self._in is None:
            return
        try:
            self._in.put_nowait(chunk)
        except queue_mod.Full:
            pass

    def poll(self) -> list[tuple[float, bool]]:
        """Return [(wall_time, is_downbeat), ...] detected since last poll."""
        events = []
        if self._out is None or self._failed:
            return events
        while True:
            try:
                kind, payload = self._out.get_nowait()
            except queue_mod.Empty:
                break
            if kind == "ready":
                self.available = True
                print("[BeatNet] Ready")
            elif kind == "error":
                self._failed = True
                self.available = False
                print(f"[BeatNet] {payload} - falling back to aubio/internal tracker")
            elif kind == "beat":
                events.append(payload)
        return events

    def stop(self) -> None:
        if self._stop is not None:
            self._stop.set()
        if self._in is not None:
            try:
                self._in.put_nowait(None)
            except queue_mod.Full:
                pass
        if self._process is not None:
            self._process.join(timeout=3.0)
            if self._process.is_alive():
                self._process.terminate()
        print("[BeatNet] Stopped")
