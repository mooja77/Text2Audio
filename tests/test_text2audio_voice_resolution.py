import os

import pytest
from fastapi.testclient import TestClient

import backend.render as render
from backend.render import UnknownVoiceError, resolve_synthesizer


class _Store:
    def __init__(self, metas):
        self.metas = metas

    def get(self, voice_id):
        return self.metas.get(voice_id)

    def ref_path(self, voice_id):
        return f"/refs/{voice_id}.wav"


def test_text2audio_resolver_preset_uses_factory():
    seen = {}

    def factory(voice_id, speed):
        seen["args"] = (voice_id, speed)
        return "synth"

    assert resolve_synthesizer("af_heart", 1.1, _Store({}), factory=factory) == "synth"
    assert seen["args"] == ("af_heart", 1.1)


def test_text2audio_resolver_clone_builds_cloned_synth(monkeypatch):
    captured = {}

    class FakeCloned:
        def __init__(self, ref, text, speed):
            captured.update(ref=ref, text=text, speed=speed)

    monkeypatch.setattr(render, "ClonedSynthesizer", FakeCloned)
    store = _Store({"v0a1b2c3d4": {"refText": "hello"}})
    out = resolve_synthesizer("v0a1b2c3d4", 0.9, store)
    assert isinstance(out, FakeCloned)
    assert captured == {"ref": "/refs/v0a1b2c3d4.wav", "text": "hello", "speed": 0.9}


def test_text2audio_resolver_unknown_raises_unknown_voice_error():
    with pytest.raises(UnknownVoiceError) as exc:
        resolve_synthesizer("nope", 1.0, _Store({}))
    assert exc.value.voice_id == "nope"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("T2A_LIBRARY_DIR", str(tmp_path / "library"))
    import importlib, server
    importlib.reload(server)
    with TestClient(server.app) as c:
        yield c


def test_text2audio_unknown_voice_422_has_no_side_effects(client):
    import server
    before = sorted(os.listdir(server.library.base))
    r = client.post("/api/render", json={"bookText": "## A\n\nhi", "voice": "does_not_exist"})
    assert r.status_code == 422
    assert r.json() == {"error": "unknown voice", "voice": "does_not_exist"}
    assert sorted(os.listdir(server.library.base)) == before
