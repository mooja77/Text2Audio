import io
import json
import os

import numpy as np
import soundfile as sf
import pytest

import pipeline.clone_synth as cs
from pipeline.clone_synth import ClonedSynthesizer, _start_worker
from pipeline.synth import BaseSynthesizer, SAMPLE_RATE, SENTENCE_GAP


def test_cloned_is_base_synthesizer():
    assert issubclass(ClonedSynthesizer, BaseSynthesizer)


def test_paragraph_logic_inherited(monkeypatch):
    s = ClonedSynthesizer.__new__(ClonedSynthesizer)  # bypass worker spawn
    monkeypatch.setattr(s, "synth_chunk", lambda t: np.ones(100, dtype=np.float32))
    out = s.synth_paragraphs([["a", "b"]])
    assert out.shape[0] == 100 + int(SENTENCE_GAP * SAMPLE_RATE) + 100


def test_resample_changes_length():
    out = cs._resample(np.ones(1000, dtype=np.float32), 16000, 24000)
    assert out.shape[0] == 1500


class _FakeProc:
    """Stands in for the F5 worker subprocess."""
    def __init__(self, ready_line, resp_line):
        self._lines = [ready_line, resp_line]
        self.stdin = io.StringIO()
        self.stdout = self
        self._killed = False

    def readline(self):
        return self._lines.pop(0) if self._lines else ""

    def poll(self):
        return None

    def kill(self):
        self._killed = True


def test_start_worker_raises_when_f5_missing(monkeypatch):
    # worker that never prints {"ready": true} -> install error
    def fake_popen(*a, **k):
        return _FakeProc(ready_line="", resp_line="")
    monkeypatch.setattr(cs.subprocess, "Popen", fake_popen)
    with pytest.raises(RuntimeError, match="f5-tts"):
        _start_worker()


def test_synth_chunk_round_trips_via_worker(monkeypatch, tmp_path):
    wavpath = str(tmp_path / "out.wav")
    sf.write(wavpath, np.ones(1200, dtype=np.float32), SAMPLE_RATE)
    proc = _FakeProc(ready_line=json.dumps({"ready": True}) + "\n",
                     resp_line=json.dumps({"wav": wavpath, "sr": SAMPLE_RATE}) + "\n")
    monkeypatch.setattr(cs.subprocess, "Popen", lambda *a, **k: proc)
    s = ClonedSynthesizer("ref.wav", ref_text="hi", speed=1.0)  # consumes ready_line
    out = s.synth_chunk("hello")
    assert out.shape[0] == 1200  # 24k -> 24k, no resample
    assert not os.path.exists(wavpath)  # worker temp wav is cleaned up


@pytest.mark.skipif(os.environ.get("RUN_F5") != "1",
                    reason="Set RUN_F5=1 to run the real F5 subprocess smoke test")
def test_f5_smoke(tmp_path):
    ref = str(tmp_path / "ref.wav")
    sf.write(ref, np.zeros(SAMPLE_RATE, dtype=np.float32), SAMPLE_RATE)
    s = ClonedSynthesizer(ref, ref_text="hello there friend", speed=1.0)
    audio = s.synth_chunk("Hello there, this is a test.")
    assert isinstance(audio, np.ndarray) and audio.shape[0] > 0
