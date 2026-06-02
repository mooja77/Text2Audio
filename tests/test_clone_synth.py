import numpy as np
import pytest

from pipeline.clone_synth import ClonedSynthesizer, _get_model
import pipeline.clone_synth as cs
from pipeline.synth import BaseSynthesizer, SAMPLE_RATE, SENTENCE_GAP


def test_cloned_is_base_synthesizer():
    assert issubclass(ClonedSynthesizer, BaseSynthesizer)


def test_paragraph_logic_inherited(monkeypatch):
    s = ClonedSynthesizer.__new__(ClonedSynthesizer)  # bypass model load
    monkeypatch.setattr(s, "synth_chunk", lambda t: np.ones(100, dtype=np.float32))
    out = s.synth_paragraphs([["a", "b"]])
    assert out.shape[0] == 100 + int(SENTENCE_GAP * SAMPLE_RATE) + 100


def test_missing_f5_raises_clear_error(monkeypatch):
    cs._MODEL = None
    def boom():
        raise ImportError("no f5")
    monkeypatch.setattr(cs, "_import_f5", boom)
    with pytest.raises(RuntimeError, match="f5-tts"):
        _get_model()


def test_resample_changes_length():
    out = cs._resample(np.ones(1000, dtype=np.float32), 16000, 24000)
    assert out.shape[0] == 1500


@pytest.mark.skipif(__import__("os").environ.get("RUN_F5") != "1",
                    reason="Set RUN_F5=1 to run the F5 model smoke test")
def test_f5_smoke(tmp_path):
    import soundfile as sf
    ref = str(tmp_path / "ref.wav")
    sf.write(ref, np.zeros(SAMPLE_RATE, dtype=np.float32), SAMPLE_RATE)
    s = ClonedSynthesizer(ref, ref_text="", speed=1.0)
    audio = s.synth_chunk("Hello there, this is a test.")
    assert isinstance(audio, np.ndarray) and audio.shape[0] > 0
