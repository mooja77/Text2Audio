"""Neural-engine synthesis (studio voices and voice cloning), isolated in a subprocess.

The heavy neural engine runs in a child process (pipeline.engine_worker) that never
co-resides with the server's Kokoro stack, so its memory is freed when a render ends
and a native crash cannot take the server down. The engine is only imported inside
the worker.
"""
import json
import os
import subprocess
import sys
import queue
import threading

import numpy as np
import soundfile as sf

from pipeline.synth import BaseSynthesizer, FatalSynthError, SAMPLE_RATE
from pipeline.engines import DEFAULT_ENGINE, INSTALL_HINT

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER_START_TIMEOUT = float(os.environ.get("T2A_ENGINE_START_TIMEOUT", "600"))
WORKER_CHUNK_TIMEOUT = float(os.environ.get("T2A_ENGINE_CHUNK_TIMEOUT", "600"))


def _readline_with_timeout(stream, timeout: float) -> str:
    result = queue.Queue(maxsize=1)

    def read():
        try:
            result.put((stream.readline(), None))
        except Exception as exc:
            result.put(("", exc))

    threading.Thread(target=read, daemon=True).start()
    try:
        line, error = result.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError from exc
    if error:
        raise error
    return line


def _terminate(proc) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.kill()
        proc.wait(timeout=5)
    except Exception:
        pass


def _resample(wav: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return np.asarray(wav, dtype=np.float32)
    n_out = int(round(len(wav) * sr_out / sr_in))
    x = np.linspace(0, len(wav), n_out, endpoint=False)
    return np.interp(x, np.arange(len(wav)), wav).astype(np.float32)


def _worker_env() -> dict:
    """Explicit copy of the environment, so the worker gets the offline flags
    set at startup rather than relying on implicit inheritance."""
    return dict(os.environ)


def _start_worker(engine: str = DEFAULT_ENGINE):
    """Spawn the isolated engine worker; raise a clear error if it can't load."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "pipeline.engine_worker", engine],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
        cwd=_PROJECT_ROOT, env=_worker_env())
    while True:
        try:
            line = _readline_with_timeout(proc.stdout, WORKER_START_TIMEOUT)
        except TimeoutError as exc:
            _terminate(proc)
            raise RuntimeError(f"{engine} model startup timed out") from exc
        if not line:  # worker exited before signalling ready (e.g. engine not installed)
            _terminate(proc)
            raise RuntimeError(INSTALL_HINT)
        try:
            if json.loads(line).get("ready") is True:
                return proc
        except Exception:
            continue  # ignore any stray non-protocol line


class NeuralSynthesizer(BaseSynthesizer):
    """A studio voice (``voice``) or a cloned voice (``ref_wav``) on the neural engine."""

    def __init__(self, voice: str | None = None, ref_wav: str | None = None,
                 ref_text: str = "", speed: float = 1.0, engine: str = DEFAULT_ENGINE):
        self.voice = voice
        self.ref_wav = ref_wav
        self.ref_text = ref_text or ""
        self.speed = float(speed)
        self.engine = engine
        self._proc = _start_worker(engine)

    def synth_chunk(self, text: str) -> np.ndarray:
        req = {"text": text, "voice": self.voice, "ref": self.ref_wav,
               "ref_text": self.ref_text, "speed": self.speed}
        try:
            self._proc.stdin.write(json.dumps(req) + "\n")
            self._proc.stdin.flush()
            line = _readline_with_timeout(self._proc.stdout, WORKER_CHUNK_TIMEOUT)
        except TimeoutError as exc:
            _terminate(self._proc)
            raise FatalSynthError("voice engine synthesis timed out") from exc
        except OSError as exc:  # broken pipe — worker is gone
            raise FatalSynthError("voice engine worker exited unexpectedly") from exc
        if not line:
            # Worker died: fatal and unrecoverable — abort rather than retry/skip.
            raise FatalSynthError("voice engine worker exited unexpectedly")
        try:
            resp = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FatalSynthError("voice engine worker returned an invalid response") from exc
        if "error" in resp:
            # A per-chunk model error: let the base class retry once, then abort.
            raise RuntimeError(f"voice engine synthesis failed: {resp['error']}")
        wav, sr = sf.read(resp["wav"], dtype="float32")
        try:
            os.remove(resp["wav"])
        except OSError:
            pass
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        return _resample(wav, sr, SAMPLE_RATE)

    def close(self) -> None:
        proc = getattr(self, "_proc", None)
        if proc is not None and proc.poll() is None:
            try:
                proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                proc.stdin.flush()
                proc.wait(timeout=3)
            except Exception:
                _terminate(proc)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


class ClonedSynthesizer(NeuralSynthesizer):
    """A user's cloned voice: the neural engine conditioned on a reference clip."""

    def __init__(self, ref_wav: str, ref_text: str = "", speed: float = 1.0):
        super().__init__(ref_wav=ref_wav, ref_text=ref_text, speed=speed)
