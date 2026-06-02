"""F5-TTS voice cloning, isolated in a subprocess.

F5-TTS and Kokoro segfault when loaded in the same process, so cloning runs in a
child process (pipeline.f5_worker) that never co-resides with the server's Kokoro
stack. F5 is heavy and optional — it is only imported inside the worker.
"""
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

from pipeline.synth import BaseSynthesizer, SAMPLE_RATE

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resample(wav: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return np.asarray(wav, dtype=np.float32)
    n_out = int(round(len(wav) * sr_out / sr_in))
    x = np.linspace(0, len(wav), n_out, endpoint=False)
    return np.interp(x, np.arange(len(wav)), wav).astype(np.float32)


def _start_worker():
    """Spawn the isolated F5 worker; raise a clear error if F5 can't load."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "pipeline.f5_worker"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
        cwd=_PROJECT_ROOT)
    while True:
        line = proc.stdout.readline()
        if not line:  # worker exited before signalling ready (e.g. f5 not installed)
            try:
                proc.kill()
            except Exception:
                pass
            raise RuntimeError("install f5-tts to use cloned voices")
        try:
            if json.loads(line).get("ready") is True:
                return proc
        except Exception:
            continue  # ignore any stray non-protocol line


class ClonedSynthesizer(BaseSynthesizer):
    def __init__(self, ref_wav: str, ref_text: str = "", speed: float = 1.0):
        self.ref_wav = ref_wav
        self.ref_text = ref_text or ""
        self.speed = float(speed)
        self._proc = _start_worker()

    def synth_chunk(self, text: str) -> np.ndarray:
        req = {"ref": self.ref_wav, "ref_text": self.ref_text,
               "text": text, "speed": self.speed}
        self._proc.stdin.write(json.dumps(req) + "\n")
        self._proc.stdin.flush()
        line = self._proc.stdout.readline()
        if not line:
            raise RuntimeError("f5 worker exited unexpectedly")
        resp = json.loads(line)
        wav, sr = sf.read(resp["wav"], dtype="float32")
        try:
            os.remove(resp["wav"])
        except OSError:
            pass
        return _resample(wav, sr, SAMPLE_RATE)

    def close(self) -> None:
        proc = getattr(self, "_proc", None)
        if proc is not None and proc.poll() is None:
            try:
                proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                proc.stdin.flush()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
