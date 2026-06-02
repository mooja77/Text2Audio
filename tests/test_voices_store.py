import os
import numpy as np
import soundfile as sf
import pytest

from backend.voices import VoiceStore, new_voice_id


def _wav_bytes(tmp_path):
    p = tmp_path / "src.wav"
    sf.write(str(p), np.zeros(16000, dtype=np.float32), 16000)  # 1s @16k mono
    return p.read_bytes()


def test_new_voice_id_unique():
    assert new_voice_id() != new_voice_id()


def test_create_list_get_delete(tmp_path):
    store = VoiceStore(str(tmp_path / "voices"))
    assert store.list() == []
    v = store.create("My Voice", _wav_bytes(tmp_path), ".wav", ref_text="hello")
    assert v["name"] == "My Voice" and v["refText"] == "hello"
    rp = store.ref_path(v["id"])
    assert os.path.isfile(rp)
    info = sf.info(rp)
    assert info.samplerate == 24000 and info.channels == 1
    assert [x["id"] for x in store.list()] == [v["id"]]
    assert store.get(v["id"])["name"] == "My Voice"
    store.delete(v["id"])
    assert store.get(v["id"]) is None


def test_create_rejects_unreadable_audio(tmp_path):
    store = VoiceStore(str(tmp_path / "voices"))
    with pytest.raises(ValueError):
        store.create("Bad", b"not audio at all", ".wav", ref_text="")
