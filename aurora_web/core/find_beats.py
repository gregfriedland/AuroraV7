"""External beat-onset feed compatible with AuroraV6 findBeatsCmd."""

import subprocess
import threading
import time


class ExternalBeatFeed:
    """Read V6-style onset lines from an external command.

    The command should write lines like ``[01001]``. Onsets remain active for
    ``onset_duration`` seconds after the last valid line.
    """

    def __init__(self, command: str, onset_duration: float = 0.2, verbose: bool = True):
        self.command = command
        self.onset_duration = onset_duration
        self.verbose = verbose

        self._process: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._last_onset_time = 0.0
        self._onsets: tuple[bool, ...] = ()

    def start(self) -> None:
        """Start the external beat command."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._process = subprocess.Popen(
            self.command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        print(f"[FindBeats] Started: {self.command}")

    def _read_loop(self) -> None:
        if not self._process or not self._process.stdout:
            return

        while not self._stop_event.is_set():
            line = self._process.stdout.readline()
            if line == "":
                if self._process.poll() is not None:
                    break
                time.sleep(0.01)
                continue
            self._set_from_line(line.strip())

        print("[FindBeats] Stopped")

    def _set_from_line(self, line: str) -> None:
        if len(line) < 2 or line[0] != "[" or line[-1] != "]":
            if self.verbose:
                print(f"[FindBeats] Invalid onset line: {line}")
            return

        values = []
        for char in line[1:-1]:
            if char not in ("0", "1"):
                if self.verbose:
                    print(f"[FindBeats] Invalid onset line: {line}")
                return
            values.append(char == "1")

        with self._lock:
            self._onsets = tuple(values)
            self._last_onset_time = time.monotonic()

    def get_onsets(self) -> tuple[bool, ...]:
        """Return current onsets, or all-false after the onset window expires."""
        with self._lock:
            onsets = self._onsets
            last_onset_time = self._last_onset_time

        if not onsets:
            return ()
        if time.monotonic() - last_onset_time > self.onset_duration:
            return tuple(False for _ in onsets)
        return onsets

    def stop(self) -> None:
        """Stop the external beat command."""
        self._stop_event.set()
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
