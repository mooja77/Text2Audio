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
    """Stands in for the engine worker subprocess."""
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


def test_start_worker_raises_install_hint_when_engine_missing(monkeypatch):
    # worker that never prints {"ready": true} -> install error
    from pipeline.engines import INSTALL_HINT
    def fake_popen(*a, **k):
        return _FakeProc(ready_line="", resp_line="")
    monkeypatch.setattr(cs.subprocess, "Popen", fake_popen)
    with pytest.raises(RuntimeError) as exc:
        _start_worker()
    assert str(exc.value) == INSTALL_HINT


def test_worker_is_started_with_the_engine_name(monkeypatch):
    from pipeline.engines import DEFAULT_ENGINE
    seen = {}
    def fake_popen(cmd, **k):
        seen["cmd"] = cmd
        return _FakeProc(json.dumps({"ready": True}) + "\n", "")
    monkeypatch.setattr(cs.subprocess, "Popen", fake_popen)
    _start_worker()
    assert seen["cmd"][-2:] == ["pipeline.engine_worker", DEFAULT_ENGINE]


def test_preset_voice_request_names_the_voice(monkeypatch, tmp_path):
    wavpath = str(tmp_path / "out.wav")
    sf.write(wavpath, np.ones(480, dtype=np.float32), 48000)  # resampled to 24 kHz
    proc = _FakeProc(ready_line=json.dumps({"ready": True}) + "\n",
                     resp_line=json.dumps({"wav": wavpath, "sr": 48000}) + "\n")
    monkeypatch.setattr(cs.subprocess, "Popen", lambda *a, **k: proc)
    s = cs.NeuralSynthesizer(voice="studio_voice", speed=1.1)
    out = s.synth_chunk("hello")
    req = json.loads(proc.stdin.getvalue().splitlines()[0])
    assert req == {"text": "hello", "voice": "studio_voice", "ref": None, "ref_text": "",
                   "speed": 1.1}
    assert out.shape[0] == 240


def test_engine_error_reply_is_retried_then_aborts(monkeypatch):
    from pipeline.synth import ChunkSynthError
    s = ClonedSynthesizer.__new__(ClonedSynthesizer)
    s.voice, s.ref_wav, s.ref_text, s.speed = None, "ref.wav", "", 1.0
    lines = [json.dumps({"error": "RuntimeError: bad"}) + "\n"] * 2
    s._proc = _FakeProc(*lines)
    with pytest.raises(ChunkSynthError, match="bad"):
        s.synth_chunks(["text"])


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


def test_worker_timeout_becomes_fatal_error(monkeypatch):
    from pipeline.synth import FatalSynthError
    s = ClonedSynthesizer.__new__(ClonedSynthesizer)
    s.voice, s.ref_wav, s.ref_text, s.speed = None, "ref.wav", "", 1.0
    s._proc = _FakeProc("", "")
    monkeypatch.setattr(cs, "_readline_with_timeout",
                        lambda *a, **k: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(FatalSynthError, match="timed out"):
        s.synth_chunk("hello")


@pytest.mark.skipif(os.environ.get("RUN_CHATTERBOX") != "1",
                    reason="Set RUN_CHATTERBOX=1 to run the real Chatterbox worker smoke test")
def test_chatterbox_smoke(tmp_path):
    from pipeline.clone_synth import NeuralSynthesizer
    studio = NeuralSynthesizer(voice="studio_narrator", speed=1.0)
    try:
        audio = studio.synth_chunk("Hello there, this is the studio narrator.")
    finally:
        studio.close()
    assert isinstance(audio, np.ndarray) and audio.shape[0] > SAMPLE_RATE // 2
    ref = str(tmp_path / "ref.wav")  # a few seconds of the studio voice as the reference
    sf.write(ref, audio if len(audio) > 6 * SAMPLE_RATE else np.tile(audio, 4), SAMPLE_RATE)
    clone = ClonedSynthesizer(ref, speed=1.1)
    try:
        cloned = clone.synth_chunk("And this is the same voice, cloned.")
    finally:
        clone.close()
    assert cloned.shape[0] > SAMPLE_RATE // 2
