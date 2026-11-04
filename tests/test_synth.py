import os
import numpy as np
import pytest

from pipeline.synth import SAMPLE_RATE, PRESET_VOICES, concat_with_gaps


def test_sample_rate_is_24000():
    assert SAMPLE_RATE == 24000


def test_preset_voices_lang_codes_match_prefix():
    assert PRESET_VOICES["af_heart"] == "a"
    assert PRESET_VOICES["bf_emma"] == "b"
    # Every voice's lang_code equals the first letter of its id.
    assert all(lang == vid[0] for vid, lang in PRESET_VOICES.items())


def test_concat_with_gaps_empty():
    out = concat_with_gaps([])
    assert isinstance(out, np.ndarray)
    assert out.shape == (0,)


def test_concat_with_gaps_inserts_silence_between():
    a = np.ones(100, dtype=np.float32)
    b = np.ones(200, dtype=np.float32)
    gap_samples = int(0.5 * SAMPLE_RATE)
    out = concat_with_gaps([a, b], gap_seconds=0.5)
    assert out.shape[0] == 100 + gap_samples + 200
    # The gap region between the two clips is silent.
    assert np.all(out[100:100 + gap_samples] == 0.0)


def test_concat_with_gaps_single_array_no_gap():
    a = np.ones(50, dtype=np.float32)
    assert concat_with_gaps([a], gap_seconds=0.5).shape[0] == 50


@pytest.mark.skipif(os.environ.get("RUN_KOKORO") != "1",
                    reason="Set RUN_KOKORO=1 to run the GPU model smoke test")
def test_synthesizer_smoke():
    from pipeline.synth import Synthesizer
    synth = Synthesizer(voice="af_heart", lang_code="a")
    audio = synth.synth_chunk("Hello, this is a test.")
    assert isinstance(audio, np.ndarray)
    assert audio.shape[0] > SAMPLE_RATE // 4  # at least ~0.25s of audio


from pipeline.synth import SENTENCE_GAP, PARAGRAPH_GAP


def test_gap_constants():
    assert SENTENCE_GAP == 0.15 and PARAGRAPH_GAP == 0.6


def test_synth_paragraphs_uses_variable_gaps(monkeypatch):
    from pipeline.synth import Synthesizer

    # Build a Synthesizer without importing kokoro: bypass __init__.
    synth = Synthesizer.__new__(Synthesizer)
    synth.voice, synth.speed = "x", 1.0
    # one fixed 1000-sample clip per chunk
    monkeypatch.setattr(synth, "synth_chunk", lambda text: np.ones(1000, dtype=np.float32))

    # two paragraphs, one chunk each -> clipA + PARAGRAPH_GAP + clipB
    out = synth.synth_paragraphs([["a"], ["b"]])
    expected = 1000 + int(PARAGRAPH_GAP * SAMPLE_RATE) + 1000
    assert out.shape[0] == expected

    # one paragraph, two chunks -> clip + SENTENCE_GAP + clip
    out2 = synth.synth_paragraphs([["a", "b"]])
    expected2 = 1000 + int(SENTENCE_GAP * SAMPLE_RATE) + 1000
    assert out2.shape[0] == expected2


def test_base_synthesizer_provides_paragraph_logic():
    from pipeline.synth import BaseSynthesizer

    class Tiny(BaseSynthesizer):
        def synth_chunk(self, text):
            return np.ones(100, dtype=np.float32)

    s = Tiny()
    # one paragraph, two chunks -> 100 + SENTENCE_GAP + 100
    from pipeline.synth import SENTENCE_GAP
    out = s.synth_paragraphs([["a", "b"]])
    assert out.shape[0] == 100 + int(SENTENCE_GAP * SAMPLE_RATE) + 100
    # preview uses synth_chunk
    assert s.preview("hi").shape[0] == 100


def test_kokoro_synthesizer_is_base_subclass():
    from pipeline.synth import Synthesizer, BaseSynthesizer
    assert issubclass(Synthesizer, BaseSynthesizer)


def test_fatal_synth_error_not_swallowed():
    import pytest
    from pipeline.synth import BaseSynthesizer, FatalSynthError

    class Boom(BaseSynthesizer):
        def synth_chunk(self, text):
            raise FatalSynthError("worker dead")

    with pytest.raises(FatalSynthError):
        Boom().synth_paragraphs([["a", "b"]])
    with pytest.raises(FatalSynthError):
        Boom().synth_chunks(["a"])


def test_nonfatal_chunk_failure_retries_then_aborts():
    from pipeline.synth import BaseSynthesizer, ChunkSynthError

    class Boom(BaseSynthesizer):
        calls = 0
        def synth_chunk(self, text):
            self.calls += 1
            raise RuntimeError("model failure")

    synth = Boom()
    with pytest.raises(ChunkSynthError, match="model failure"):
        synth.synth_chunks(["must not disappear"])
    assert synth.calls == 2


def test_empty_chunk_audio_aborts():
    from pipeline.synth import BaseSynthesizer, ChunkSynthError

    class Empty(BaseSynthesizer):
        def synth_chunk(self, text):
            return np.zeros(0, dtype=np.float32)

    with pytest.raises(ChunkSynthError, match="empty audio"):
        Empty().synth_paragraphs([["text"]])


def test_select_device_cpu_fallback(monkeypatch):
    import sys, types
    from pipeline.synth import select_device
    cuda = types.SimpleNamespace(is_available=lambda: False)
    mps = types.SimpleNamespace(is_available=lambda: False)
    monkeypatch.delenv("T2A_DEVICE", raising=False)
    monkeypatch.setitem(sys.modules, "torch",
                        types.SimpleNamespace(cuda=cuda, backends=types.SimpleNamespace(mps=mps)))
    assert select_device() == "cpu"


def test_select_device_env_override(monkeypatch):
    from pipeline.synth import select_device
    monkeypatch.setenv("T2A_DEVICE", "mps")
    assert select_device() == "mps"
    monkeypatch.setenv("T2A_DEVICE", "invalid")
    with pytest.raises(ValueError):
        select_device()


def _pinned_kokoro(tmp_path, monkeypatch, voice="af_heart"):
    import hashlib
    from backend import model_download as md
    data = {"config.json": b'{"a": 1}', "kokoro-v1_0.pth": b"weights", f"voices/{voice}.pt": b"voice"}
    specs = tuple(md.Spec(r, len(b), hashlib.sha256(b).hexdigest()) for r, b in data.items())
    monkeypatch.setattr(md, "MANIFEST", {md.KOKORO_REPO: (md.KOKORO_REV, specs)})
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    for rel, b in data.items():
        p = md.local_path(str(tmp_path / "hub"), md.KOKORO_REPO, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(b)
    return md


def _fake_kokoro(monkeypatch):
    import sys
    import types
    calls = []

    class KModel:
        def __init__(self, **kw):
            calls.append(("KModel", kw))

        def to(self, device):
            calls.append(("to", device))
            return self

        def eval(self):
            return self

    class KPipeline:
        def __init__(self, **kw):
            calls.append(("KPipeline", kw))

    mod = types.ModuleType("kokoro")
    mod.KModel, mod.KPipeline = KModel, KPipeline
    monkeypatch.setitem(sys.modules, "kokoro", mod)
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)  # any Hub import fails
    import backend.offline as off
    monkeypatch.setattr(off, "ensure_voice_available",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no Hub fetch")))
    return calls


def test_synthesizer_builds_real_kokoro_objects_from_local_pinned_files(tmp_path, monkeypatch):
    from pipeline.synth import Synthesizer
    md = _pinned_kokoro(tmp_path, monkeypatch)
    calls = _fake_kokoro(monkeypatch)
    s = Synthesizer(voice="af_heart", lang_code="a", device="cpu")
    paths = md.kokoro_paths()
    assert calls[0] == ("KModel", {"config": paths["config"], "model": paths["model"],
                                   "repo_id": "hexgrad/Kokoro-82M"})
    assert calls[1] == ("to", "cpu")
    name, kw = calls[2]
    assert name == "KPipeline" and kw["lang_code"] == "a" and kw["device"] == "cpu"
    assert kw["model"] is not None and set(kw) == {"lang_code", "model", "device"}
    assert s.voice == paths["voice"]("af_heart")


def test_synthesizer_rejects_same_size_corrupt_weights_before_construction(tmp_path, monkeypatch):
    from pipeline.synth import Synthesizer
    md = _pinned_kokoro(tmp_path, monkeypatch)
    calls = _fake_kokoro(monkeypatch)
    with open(md.kokoro_paths()["model"], "wb") as f:
        f.write(b"weighTs")  # same size as b"weights"
    with pytest.raises(md.ModelUnavailable, match="kokoro-v1_0.pth"):
        Synthesizer(voice="af_heart", lang_code="a", device="cpu")
    assert calls == []


def test_synthesizer_requires_the_selected_local_voice(tmp_path, monkeypatch):
    from pipeline.synth import Synthesizer
    md = _pinned_kokoro(tmp_path, monkeypatch)
    calls = _fake_kokoro(monkeypatch)
    os.remove(md.kokoro_paths()["voice"]("af_heart"))
    with pytest.raises(md.ModelUnavailable, match="voices/af_heart.pt"):
        Synthesizer(voice="af_heart", lang_code="a", device="cpu")
    with pytest.raises(md.ModelUnavailable, match="model_download"):
        Synthesizer(voice="am_adam", lang_code="a", device="cpu")
    assert calls == []
