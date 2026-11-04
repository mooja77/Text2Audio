"""The engine worker's request loop, driven with a fake engine (no models)."""
import io
import json

import numpy as np
import soundfile as sf

from pipeline import engine_worker


class FakeEngine:
    sample_rate = 24000

    def __init__(self):
        self.calls = []

    def synth(self, text, voice=None, ref=None, ref_text=""):
        self.calls.append({"text": text, "voice": voice, "ref": ref, "ref_text": ref_text})
        if text == "boom":
            raise RuntimeError("model failure")
        return np.ones(2400, dtype=np.float32), 24000


def _run(lines, engine):
    out = io.StringIO()
    engine_worker.serve(engine, io.StringIO("".join(json.dumps(l) + "\n" for l in lines)), out)
    return [json.loads(l) for l in out.getvalue().splitlines()]


def test_serve_announces_ready_then_answers_each_request():
    eng = FakeEngine()
    replies = _run([{"text": "hello", "voice": "aria"},
                    {"text": "clone me", "ref": "r.wav", "ref_text": "hi"},
                    {"cmd": "quit"}, {"text": "never"}], eng)
    assert replies[0] == {"ready": True}
    assert [c["text"] for c in eng.calls] == ["hello", "clone me"]
    assert eng.calls[0]["voice"] == "aria" and eng.calls[1]["ref"] == "r.wav"
    for r in replies[1:]:
        wav, sr = sf.read(r["wav"], dtype="float32")
        assert sr == 24000 and len(wav) == 2400
        import os
        os.remove(r["wav"])


def test_serve_reports_errors_without_dying():
    eng = FakeEngine()
    replies = _run([{"text": "boom"}, {"text": "fine"}], eng)
    assert "model failure" in replies[1]["error"]
    assert "wav" in replies[2]
    import os
    os.remove(replies[2]["wav"])


def test_speed_is_applied_by_time_stretch():
    eng = FakeEngine()
    replies = _run([{"text": "fast", "speed": 1.25}], eng)
    wav, sr = sf.read(replies[1]["wav"], dtype="float32")
    import os
    os.remove(replies[1]["wav"])
    assert abs(len(wav) - 2400 / 1.25) < 300  # shorter by ~1/1.25


def test_apply_speed_is_identity_at_one():
    x = np.random.default_rng(0).standard_normal(4800).astype(np.float32)
    assert np.array_equal(engine_worker.apply_speed(x, 24000, 1.0), x)


def test_unknown_engine_name_is_rejected():
    import pytest
    with pytest.raises(ValueError, match="unknown engine"):
        engine_worker.load_engine("nope", "cpu")
