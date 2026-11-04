"""Engine registry and the Chatterbox adapter, driven with a fake model (no weights, no network)."""
import hashlib
import sys
from pathlib import Path

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


@pytest.fixture()
def pinned(tmp_path, monkeypatch):
    """Hermetic pinned Chatterbox snapshot in a tmp cache; the Hub library is unimportable."""
    from backend import model_download as md
    data = {n: b"cb:" + n.encode() for n in engines.CHATTERBOX_FILES}
    specs = tuple(md.Spec(n, len(b), hashlib.sha256(b).hexdigest()) for n, b in data.items())
    monkeypatch.setattr(md, "MANIFEST", {md.CHATTERBOX_REPO: (engines.CHATTERBOX_REVISION, specs)})
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    snap = Path(md.chatterbox_dir())
    snap.mkdir(parents=True)
    for n, b in data.items():
        (snap / n).write_bytes(b)
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)  # any Hub import now fails
    return md, snap, data


def test_load_uses_verified_pinned_directory_without_hub(monkeypatch, pinned):
    md, snap, _ = pinned
    seen = {}

    class FakeTTS:
        @classmethod
        def from_local(cls, ckpt_dir, device):
            seen["dir"], seen["device"] = ckpt_dir, device
            return FakeModel()

    monkeypatch.setattr(ce, "_chatterbox_tts", lambda: FakeTTS)
    eng = ce.load("cpu")
    assert isinstance(eng, ce.ChatterboxEngine)
    assert seen["dir"] == snap and isinstance(seen["dir"], Path) and seen["device"] == "cpu"
    assert not hasattr(ce, "_hf_hub_download")


def test_load_rejects_same_size_corruption_before_constructing(monkeypatch, pinned):
    md, snap, data = pinned
    name = engines.CHATTERBOX_FILES[1]
    bad = bytearray(data[name])
    bad[-1] ^= 1
    (snap / name).write_bytes(bytes(bad))  # same size, wrong digest

    def boom():
        raise AssertionError("model must not be constructed")

    monkeypatch.setattr(ce, "_chatterbox_tts", boom)
    with pytest.raises(md.ModelUnavailable, match="model_download") as exc:
        ce.load("cpu")
    assert name in str(exc.value)


def test_load_reports_missing_file_with_install_guidance(monkeypatch, pinned):
    md, snap, _ = pinned
    (snap / engines.CHATTERBOX_FILES[0]).unlink()
    monkeypatch.setattr(ce, "_chatterbox_tts",
                        lambda: (_ for _ in ()).throw(AssertionError("must not construct")))
    with pytest.raises(md.ModelUnavailable, match="Install Text2Audio"):
        ce.load("cpu")
