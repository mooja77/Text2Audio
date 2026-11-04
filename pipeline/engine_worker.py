"""Neural TTS engine in an isolated subprocess.

The long-running server never imports the heavy neural engine. This worker loads
one engine alone in a child process and talks to the parent over stdin/stdout:
one JSON request per line; it replies with a temp wav path the parent reads
then deletes. Keeping the engine out of the server process means its memory is
released when a render ends, a native crash cannot take the server down, and
Kokoro (the light engine) never shares a process with it.

Engines and their dependencies print progress and warnings to stdout, which would
corrupt the JSON protocol, so all library chatter goes to stderr and protocol
lines go to the *real* stdout only.

usage: python -m pipeline.engine_worker <engine>
"""
import importlib
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

from pipeline.engines import ENGINE_MODULES

# engine name -> module in pipeline.engines that defines load(device) -> engine.
# An engine object has .synth(text, voice=None, ref=None, ref_text="") -> (wav, sr).
ENGINES = dict(ENGINE_MODULES)


def load_engine(name: str, device: str):
    if name not in ENGINES:
        raise ValueError(f"unknown engine: {name}")
    return importlib.import_module(ENGINES[name]).load(device)


def apply_speed(wav: np.ndarray, sr: int, speed: float) -> np.ndarray:
    """Change tempo without changing pitch (ffmpeg atempo). Identity at 1.0."""
    wav = np.asarray(wav, dtype=np.float32)
    if abs(float(speed) - 1.0) < 1e-6 or len(wav) == 0:
        return wav
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-f", "f32le", "-ar", str(int(sr)), "-ac", "1",
         "-i", "pipe:0", "-filter:a", f"atempo={float(speed):.4f}", "-f", "f32le", "pipe:1"],
        input=wav.tobytes(), capture_output=True, check=True)
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def serve(engine, stdin, stdout) -> None:
    import soundfile as sf

    def emit(obj):
        stdout.write(json.dumps(obj) + "\n")
        stdout.flush()

    emit({"ready": True})
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        if req.get("cmd") == "quit":
            break
        try:
            wav, sr = engine.synth(req["text"], voice=req.get("voice"), ref=req.get("ref"),
                                   ref_text=req.get("ref_text") or "")
            wav = apply_speed(np.asarray(wav, dtype=np.float32).reshape(-1), sr,
                              float(req.get("speed", 1.0)))
            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            sf.write(path, wav, int(sr))
            emit({"wav": path, "sr": int(sr)})
        except Exception as exc:
            emit({"error": f"{type(exc).__name__}: {exc}"})


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    from backend.offline import configure_at_startup
    from pipeline.engines import ENGINE_REPOS
    # Before the engine (and so huggingface_hub) is imported; only offline if its files are cached.
    configure_at_startup(repos=ENGINE_REPOS.get(name, ()))
    real_out = sys.stdout
    sys.stdout = sys.stderr  # all library chatter -> stderr; protocol -> real_out
    from pipeline.synth import select_device
    engine = load_engine(name, select_device())
    serve(engine, sys.stdin, real_out)


if __name__ == "__main__":
    main()
