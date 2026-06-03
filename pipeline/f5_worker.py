"""F5-TTS synthesis in an isolated subprocess.

Loading F5-TTS and Kokoro in the same process segfaults (native stack conflict),
so the long-running server never imports f5_tts. This worker runs F5 alone in a
child process and talks to the parent over stdin/stdout: one JSON request per
line; it replies with a temp wav path the parent reads then deletes.

F5 and its deps print progress/warnings to stdout, which would corrupt the JSON
protocol — so we redirect all library chatter to stderr and emit protocol lines
on the *real* stdout only.
"""
import json
import os
import sys
import tempfile


def main() -> None:
    real_out = sys.stdout
    sys.stdout = sys.stderr  # all library chatter -> stderr; protocol -> real_out

    def emit(obj):
        real_out.write(json.dumps(obj) + "\n")
        real_out.flush()

    import numpy as np
    import soundfile as sf
    from f5_tts.api import F5TTS

    model = F5TTS()
    _silent = lambda *a, **k: None
    emit({"ready": True})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        if req.get("cmd") == "quit":
            break
        wav, sr, _ = model.infer(
            ref_file=req["ref"], ref_text=req["ref_text"], gen_text=req["text"],
            speed=req.get("speed", 1.0), show_info=_silent, progress=None)
        wav = np.asarray(wav, dtype=np.float32)
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        sf.write(path, wav, sr)
        emit({"wav": path, "sr": int(sr)})


if __name__ == "__main__":
    main()
