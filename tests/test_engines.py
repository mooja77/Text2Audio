"""Engine registry and the Chatterbox adapter, driven with a fake model (no weights)."""
import types

import numpy as np
import pytest

from pipeline import engines
from pipeline.engines import chatterbox_engine as ce


def test_default_engine_is_chatterbox_and_registered():
    from pipeline import engine_worker
    assert engines.DEFAULT_ENGINE == "chatterbox"
    assert engine_worker.ENGINES["chatterbox"] == "pipeline.engines.chatterbox_engine"
    assert engines.ENGINE_REPOS["chatterbox"] == (engines.CHATTERBOX_REPO,)


def test_weights_are_pinned_to_a_full_revision():
    assert len(engines.CHATTERBOX_REVISION) == 40
    assert set(engines.CHATTERBOX_FILES) >= {"t3_cfg.safetensors", "s3gen.safetensors",
                                            "ve.safetensors", "tokenizer.json", "conds.pt"}


def test_studio_voice_is_the_default_voice():
    assert engines.DEFAULT_STUDIO_VOICE in engines.STUDIO_VOICES
    v = engines.STUDIO_VOICES[engines.DEFAULT_STUDIO_VOICE]
    assert v["engine"] == "chatterbox" and v["label"]


class FakeModel:
    sr = 24000

    def __init__(self):
        self.conds = "builtin"
        self.prepared, self.generated = [], []

    def prepare_conditionals(self, path, exaggeration=0.5):
        self.prepared.append(path)
        self.conds = f"conds:{path}"

    def generate(self, text, **kw):
        assert "audio_prompt_path" not in kw  # the adapter manages conditionals itself
        self.generated.append((text, self.conds))
        return _Tensor(np.ones((1, 1200), dtype=np.float64))


class _Tensor:
    """Just enough of a torch tensor for the adapter (CI installs no torch)."""

    def __init__(self, a):
        self.a = a

    def detach(self):
        return self

    def float(self):
        return _Tensor(self.a.astype(np.float32))

    def cpu(self):
        return self

    def numpy(self):
        return self.a


@pytest.fixture()
def engine():
    return ce.ChatterboxEngine(FakeModel())


def test_studio_voice_uses_builtin_conditionals(engine):
    wav, sr = engine.synth("Hello.", voice=engines.DEFAULT_STUDIO_VOICE)
    assert sr == 24000 and wav.shape == (1200,) and wav.dtype == np.float32
    assert engine.model.generated[-1] == ("Hello.", "builtin")


def test_clone_prepares_reference_once_and_restores_studio_voice(engine):
    engine.synth("One.", ref="a.wav")
    engine.synth("Two.", ref="a.wav")
    assert engine.model.prepared == ["a.wav"]  # cached across chunks
    assert [c for _, c in engine.model.generated] == ["conds:a.wav", "conds:a.wav"]
    engine.synth("Three.", voice=engines.DEFAULT_STUDIO_VOICE)
    assert engine.model.generated[-1][1] == "builtin"
    engine.synth("Four.", ref="b.wav")
    assert engine.model.prepared == ["a.wav", "b.wav"]


def test_unknown_studio_voice_is_rejected(engine):
    with pytest.raises(ValueError, match="unknown studio voice"):
        engine.synth("Hi.", voice="nope")


def test_load_downloads_pinned_files_then_loads_locally(monkeypatch, tmp_path):
    seen = {"files": []}

    def fake_download(repo_id, filename, revision):
        assert repo_id == engines.CHATTERBOX_REPO and revision == engines.CHATTERBOX_REVISION
        seen["files"].append(filename)
        p = tmp_path / filename
        p.write_text("x")
        return str(p)

    class FakeTTS:
        @classmethod
        def from_local(cls, ckpt_dir, device):
            seen["dir"], seen["device"] = str(ckpt_dir), device
            return FakeModel()

    monkeypatch.setattr(ce, "_hf_hub_download", lambda: fake_download)
    monkeypatch.setattr(ce, "_chatterbox_tts", lambda: FakeTTS)
    eng = ce.load("cpu")
    assert isinstance(eng, ce.ChatterboxEngine)
    assert seen["files"] == list(engines.CHATTERBOX_FILES)
    assert seen["dir"] == str(tmp_path) and seen["device"] == "cpu"
