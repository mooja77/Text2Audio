import os
import pytest
import numpy as np
from backend.library import Library
from backend import model_download as md
from backend import offline as off
from pipeline.engines import CHATTERBOX_FILES as _CBF, CHATTERBOX_REVISION as _CBREV


def _mk_specs(data):
    import hashlib
    return tuple(md.Spec(r, len(b), hashlib.sha256(b).hexdigest()) for r, b in data.items())


_KOKORO_DATA = {"config.json": b'{"a": 1}', "kokoro-v1_0.pth": b"weights",
                "voices/af_heart.pt": b"v1", "voices/am_adam.pt": b"v2"}
_CB_DATA = {n: b"cb:" + n.encode() for n in _CBF}


@pytest.fixture(autouse=True)
def _hermetic_pinned_models(tmp_path, monkeypatch):
    """Tiny pinned manifest + tmp HF cache: never sees the host cache or the network."""
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hf" / "hub"))
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    monkeypatch.setattr(md, "MANIFEST", {md.KOKORO_REPO: (md.KOKORO_REV, _mk_specs(_KOKORO_DATA)),
                                         md.CHATTERBOX_REPO: (_CBREV, _mk_specs(_CB_DATA))})
    monkeypatch.setattr(md, "language_ready", lambda: True)
    off._VERIFIED.clear()
from backend.render import render_audiobook, remaster, purge_wavs
from pipeline.synth import SAMPLE_RATE


class FakeSynth:
    def __init__(self, voice_id, speed=1.0):
        self.voice = voice_id
    def synth_chunks(self, chunks, progress=None):
        return np.zeros(int(0.2 * SAMPLE_RATE) * max(1, len(chunks)), dtype=np.float32)
    def synth_paragraphs(self, paragraphs, progress=None):
        n = sum(len(p) for p in paragraphs)
        return np.zeros(int(0.2 * SAMPLE_RATE) * max(1, n), dtype=np.float32)


def test_render_creates_m4b_and_manifest(tmp_path):
    lib = Library(str(tmp_path))
    book = "## Chapter 1 - One\nChapter 1. One.\n\nHello.\n\n## Chapter 2 - Two\nChapter 2. Two.\n\nWorld."
    events = []
    manifest = render_audiobook(
        book_text=book, voice="bm_george", speed=0.9, title="Test Book", author="Me",
        cover_path=None, library=lib, job_id="job1", emit=events.append, synth_factory=FakeSynth)

    import os
    assert os.path.isfile(lib.audio_path("job1"))
    assert manifest["title"] == "Test Book" and manifest["voice"] == "bm_george"
    assert len(manifest["chapters"]) == 2
    assert manifest["chapters"][0]["startMs"] == 0
    assert manifest["chapters"][1]["startMs"] == manifest["chapters"][0]["endMs"]
    # progress emitted per chapter + a terminal done
    assert any(e["type"] == "progress" for e in events)
    assert events[-1]["type"] == "done" and events[-1]["libraryId"] == "job1"
    # saved manifest matches
    assert lib.get("job1")["durationSeconds"] == manifest["durationSeconds"]


def test_render_empty_chapter_gets_silence(tmp_path):
    lib = Library(str(tmp_path))
    book = "## Empty\n\n"   # marker with no body
    manifest = render_audiobook(
        book_text=book, voice="af_heart", speed=1.0, title="E", author="",
        cover_path=None, library=lib, job_id="job2", emit=lambda e: None, synth_factory=FakeSynth)
    assert manifest["chapters"][0]["endMs"] > 0  # silence inserted, non-degenerate


class FakeSynthP(FakeSynth):
    pass


def test_render_keeps_wavs_and_marks_manifest(tmp_path):
    lib = Library(str(tmp_path))
    book = "## Chapter 1 - One\nChapter 1. One.\n\nHello there.\n\nSecond para."
    m = render_audiobook(book_text=book, voice="bm_george", speed=0.9, title="T",
                         author="", cover_path=None, library=lib, job_id="j1",
                         emit=lambda e: None, synth_factory=FakeSynthP)
    assert m["wavKept"] is True
    assert m["mastered"] is True and m["bitrate"] == "128k"
    assert len(m["wavFiles"]) == 1
    assert os.path.isfile(os.path.join(str(tmp_path), "j1", m["wavFiles"][0]))


def test_remaster_rebuilds_from_kept_wavs(tmp_path):
    lib = Library(str(tmp_path))
    book = "## Chapter 1 - One\nHi.\n\n## Chapter 2 - Two\nBye."
    render_audiobook(book_text=book, voice="af_heart", speed=1.0, title="T", author="",
                     cover_path=None, library=lib, job_id="j2", emit=lambda e: None,
                     synth_factory=FakeSynthP)
    m = remaster(lib, "j2", bitrate="96k")
    assert m["bitrate"] == "96k"
    import json
    saved = lib.get("j2")
    assert saved["bitrate"] == "96k"
    import subprocess
    probe = subprocess.run(["ffprobe", "-print_format", "json", "-show_chapters",
                            lib.audio_path("j2")], capture_output=True, text=True, check=True)
    assert len(json.loads(probe.stdout)["chapters"]) == 2


def test_purge_then_remaster_raises(tmp_path):
    lib = Library(str(tmp_path))
    render_audiobook(book_text="## A\n\nhi", voice="af_heart", speed=1.0, title="T",
                     author="", cover_path=None, library=lib, job_id="j3",
                     emit=lambda e: None, synth_factory=FakeSynthP)
    m = purge_wavs(lib, "j3")
    assert m["wavKept"] is False and m["wavFiles"] == []
    assert not os.path.isdir(os.path.join(str(tmp_path), "j3", "wav"))
    import pytest
    with pytest.raises(Exception):
        remaster(lib, "j3")


def test_render_applies_custom_pronunciations(tmp_path):
    lib = Library(str(tmp_path))
    seen = []

    class SpySynth(FakeSynth):
        def synth_paragraphs(self, paragraphs, progress=None):
            for para in paragraphs:
                seen.extend(para)
            return super().synth_paragraphs(paragraphs)

    book = "## Chapter 1 - One\nThe foo sailed in 1801."
    render_audiobook(book_text=book, voice="af_heart", speed=1.0, title="T", author="",
                     cover_path=None, library=lib, job_id="jn", emit=lambda e: None,
                     synth_factory=SpySynth, custom_rules={"foo": "bar"})
    joined = " ".join(seen)
    assert "bar" in joined and "foo" not in joined
    assert "eighteen oh-one" in joined  # built-in number expansion also ran


def test_render_factory_called_with_voice_and_speed(tmp_path):
    lib = Library(str(tmp_path))
    seen = {}

    def factory(voice_id, speed):
        seen["voice"], seen["speed"] = voice_id, speed
        return FakeSynth(voice_id, speed)

    render_audiobook(book_text="## A\n\nHello.", voice="my_clone", speed=0.9, title="T",
                     author="", cover_path=None, library=lib, job_id="jf",
                     emit=lambda e: None, synth_factory=factory)
    assert seen == {"voice": "my_clone", "speed": 0.9}
    assert lib.get("jf")["voice"] == "my_clone"


def test_render_closes_synth(tmp_path):
    lib = Library(str(tmp_path))
    closed = {"v": False}

    class ClosingSynth(FakeSynth):
        def close(self):
            closed["v"] = True

    render_audiobook(book_text="## A\n\nHi.", voice="x", speed=1.0, title="T", author="",
                     cover_path=None, library=lib, job_id="jc", emit=lambda e: None,
                     synth_factory=lambda vid, sp: ClosingSynth(vid, sp))
    assert closed["v"] is True


def test_render_aborts_on_fatal_synth_error(tmp_path):
    import pytest
    from pipeline.synth import FatalSynthError
    lib = Library(str(tmp_path))
    closed = {"v": False}

    class DeadSynth:
        def __init__(self, vid, sp=1.0):
            pass
        def synth_paragraphs(self, paragraphs, progress=None):
            raise FatalSynthError("worker died")
        def close(self):
            closed["v"] = True

    with pytest.raises(FatalSynthError):
        render_audiobook(book_text="## A\n\nHi.", voice="x", speed=1.0, title="T", author="",
                         cover_path=None, library=lib, job_id="jd", emit=lambda e: None,
                         synth_factory=lambda vid, sp: DeadSynth(vid, sp))
    assert closed["v"] is True       # closed even on failure (finally)
    assert lib.get("jd") is None     # partial workdir cleaned up


def test_real_chunk_interface_streams_progress_and_uses_cache(tmp_path):
    from pipeline.synth import BaseSynthesizer
    lib = Library(str(tmp_path / "library"))
    calls = []

    class StreamingSynth(BaseSynthesizer):
        def __init__(self, voice, speed): pass
        def synth_chunk(self, text):
            calls.append(text)
            return np.ones(1000, dtype=np.float32) * 0.01

    class MemoryCache:
        def __init__(self): self.values = {}
        def get(self, key): return self.values.get(repr(key))
        def put(self, key, audio): self.values[repr(key)] = audio

    cache = MemoryCache()
    events = []
    kwargs = dict(book_text="## A\nFirst sentence. Second sentence.", voice="af_heart",
                  speed=1.0, title="T", author="", cover_path=None, library=lib,
                  emit=events.append, synth_factory=StreamingSynth, chunk_cache=cache)
    render_audiobook(job_id="stream1", **kwargs)
    first_call_count = len(calls)
    render_audiobook(job_id="stream2", **kwargs)
    assert first_call_count > 0 and len(calls) == first_call_count
    assert any(event.get("chunkCount") for event in events)


def _block_network(monkeypatch):
    import socket
    attempts = []

    def deny(*args, **kwargs):
        attempts.append(args)
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    return attempts


def test_socket_guard_trips_on_connect(monkeypatch):
    import socket
    import pytest
    attempts = _block_network(monkeypatch)
    with pytest.raises(AssertionError, match="network access attempted"):
        socket.create_connection(("127.0.0.1", 9))
    assert len(attempts) == 1


def test_cached_render_sets_offline_and_opens_no_sockets(tmp_path, monkeypatch):
    from backend.offline import configure_at_startup
    hub = tmp_path / "hub"
    env = _kokoro_cache(tmp_path)
    configure_at_startup(env)
    assert env["HF_HUB_OFFLINE"] == "1" and env["TRANSFORMERS_OFFLINE"] == "1"

    attempts = _block_network(monkeypatch)
    lib = Library(str(tmp_path / "library"))
    manifest = render_audiobook(
        book_text="## Chapter 1 - One\nChapter 1. One.\n\nHello.", voice="af_heart",
        speed=1.0, title="T", author="", cover_path=None, library=lib, job_id="off1",
        emit=lambda e: None, synth_factory=FakeSynth)
    assert manifest["id"] == "off1"
    assert attempts == []


def _kokoro_cache(tmp_path, files=("config.json", "kokoro-v1_0.pth"), voices=("af_heart", "am_adam")):
    snap = tmp_path / "hub" / "models--hexgrad--Kokoro-82M" / "snapshots" / md.KOKORO_REV
    (snap / "voices").mkdir(parents=True)
    for name in files:
        (snap / name).write_bytes(_KOKORO_DATA[name])
    for v in voices:
        (snap / "voices" / f"{v}.pt").write_bytes(_KOKORO_DATA[f"voices/{v}.pt"])
    return {"HF_HUB_CACHE": str(tmp_path / "hub")}


def test_partial_snapshot_is_not_treated_as_cached(tmp_path):
    from backend.offline import configure_at_startup
    env = _kokoro_cache(tmp_path, files=("config.json",))  # interrupted first download
    assert configure_at_startup(env) == {}
    assert "HF_HUB_OFFLINE" not in env


def test_user_offline_setting_is_respected(tmp_path):
    from backend.offline import configure_at_startup
    env = _kokoro_cache(tmp_path)
    env["HF_HUB_OFFLINE"] = "0"
    assert configure_at_startup(env) == {}
    assert env["HF_HUB_OFFLINE"] == "0"


def test_new_voice_is_fetched_once_when_we_forced_offline(tmp_path, monkeypatch):
    import types
    import backend.offline as off
    constants = types.SimpleNamespace(HF_HUB_OFFLINE=True)  # stands in for huggingface_hub.constants
    env = _kokoro_cache(tmp_path, voices=("af_heart",))
    monkeypatch.setattr(off.os, "environ", env)
    monkeypatch.setattr(off, "_forced", True)
    seen = []

    def fake_download(repo_id, filename, revision):
        seen.append((repo_id, filename, revision, constants.HF_HUB_OFFLINE))

    assert off.ensure_voice_available("af_heart", download=fake_download, hub_constants=constants) is False  # cached
    assert off.ensure_voice_available("am_adam", download=fake_download, hub_constants=constants) is True
    assert seen == [("hexgrad/Kokoro-82M", "voices/am_adam.pt", md.KOKORO_REV, False)]  # online only during the call
    assert constants.HF_HUB_OFFLINE is True  # restored afterwards


def test_new_voice_not_fetched_when_offline_was_not_forced_by_us(tmp_path, monkeypatch):
    import backend.offline as off
    env = _kokoro_cache(tmp_path)
    monkeypatch.setattr(off.os, "environ", env)
    monkeypatch.setattr(off, "_forced", False)
    called = []
    assert off.ensure_voice_available("am_adam", download=lambda **k: called.append(k)) is False
    assert called == []


def test_uncached_models_stay_online(tmp_path):
    from backend.offline import configure_at_startup
    env = {"HF_HUB_CACHE": str(tmp_path / "empty")}
    assert configure_at_startup(env) == {}
    assert "HF_HUB_OFFLINE" not in env and "TRANSFORMERS_OFFLINE" not in env


@pytest.mark.parametrize("voice,engine", [("v0a1b2c3d4", "chatterbox"),
                                          ("studio_narrator", "chatterbox"),
                                          ("af_heart", "kokoro")])
def test_render_records_engine_and_no_noncommercial_license(tmp_path, voice, engine):
    """1.5 clones with Chatterbox (MIT): no book is marked non-commercial any more."""
    lib = Library(str(tmp_path))
    m = render_audiobook(book_text="## A\n\nHi.", voice=voice, speed=1.0, title="T",
                         author="", cover_path=None, library=lib, job_id="lic1",
                         emit=lambda e: None, synth_factory=FakeSynth)
    assert m["engine"] == engine
    assert "license" not in m and "licenseAttribution" not in m
    assert lib.get("lic1")["engine"] == engine


def test_cancelled_render_removes_partial_work(tmp_path):
    import pytest
    from backend.render import RenderCancelled
    lib = Library(str(tmp_path))
    with pytest.raises(RenderCancelled):
        render_audiobook(book_text="## A\nHello.", voice="af_heart", speed=1.0,
                         title="T", author="", cover_path=None, library=lib,
                         job_id="cancelled", emit=lambda e: None,
                         synth_factory=FakeSynth, cancelled=lambda: True)
    assert lib.get("cancelled") is None


def test_clone_worker_gets_offline_env_and_opens_no_sockets(monkeypatch):
    import json
    import io
    import pipeline.clone_synth as cs

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    attempts = _block_network(monkeypatch)
    seen = {}

    class FakeProc:
        stdin = io.StringIO()

        def __init__(self):
            self.stdout = io.StringIO(json.dumps({"ready": True}) + "\n")

        def poll(self):
            return None

        def kill(self):
            pass

    def fake_popen(*args, **kwargs):
        seen.update(kwargs)
        return FakeProc()

    monkeypatch.setattr(cs.subprocess, "Popen", fake_popen)
    cs.ClonedSynthesizer("ref.wav", ref_text="hi", speed=1.0)
    assert seen["env"]["HF_HUB_OFFLINE"] == "1"
    assert seen["env"]["TRANSFORMERS_OFFLINE"] == "1"
    assert attempts == []


def test_chatterbox_weights_count_as_cached_only_when_complete(tmp_path):
    from backend.offline import models_cached
    from pipeline.engines import CHATTERBOX_FILES, CHATTERBOX_REPO, CHATTERBOX_REVISION
    snap = (tmp_path / "hub" / "models--ResembleAI--chatterbox" / "snapshots" / CHATTERBOX_REVISION)
    snap.mkdir(parents=True)
    env = {"HF_HUB_CACHE": str(tmp_path / "hub")}
    for name in CHATTERBOX_FILES[:-1]:
        (snap / name).write_bytes(_CB_DATA[name])
    assert models_cached(env, repos=(CHATTERBOX_REPO,)) is False  # interrupted download
    (snap / CHATTERBOX_FILES[-1]).write_bytes(_CB_DATA[CHATTERBOX_FILES[-1]])
    assert models_cached(env, repos=(CHATTERBOX_REPO,)) is True


def test_cache_never_reuses_pre_1_5_audio_for_a_cloned_voice(tmp_path):
    """A 1.4 clone was narrated by F5 (CC-BY-NC). Its cached chunks must not be
    reused once the same voice id is narrated by Chatterbox, or a re-render would
    drop the non-commercial mark while still containing F5 audio."""
    from backend.render import chunk_cache_key
    from pipeline.synth import BaseSynthesizer
    lib = Library(str(tmp_path))
    text = "First sentence."
    old_key = {"version": 1, "voice": "v0a1b2c3d4", "speed": 1.0, "text": text}  # 1.4 format
    assert chunk_cache_key("v0a1b2c3d4", 1.0, text) != old_key
    assert chunk_cache_key("v0a1b2c3d4", 1.0, text)["engine"] == "chatterbox"
    # Kokoro keys are unchanged, so users keep their Kokoro cache.
    assert chunk_cache_key("af_heart", 1.0, text) == {"version": 1, "voice": "af_heart",
                                                      "speed": 1.0, "text": text}

    calls = []

    class Synth(BaseSynthesizer):
        def __init__(self, voice, speed): pass
        def synth_chunk(self, t):
            calls.append(t)
            return np.ones(1000, dtype=np.float32) * 0.01

    class MemoryCache:
        def __init__(self): self.values = {repr(old_key): np.zeros(1000, dtype=np.float32)}
        def get(self, key): return self.values.get(repr(key))
        def put(self, key, audio): self.values[repr(key)] = audio

    render_audiobook(book_text="## A\n" + text, voice="v0a1b2c3d4", speed=1.0, title="T",
                     author="", cover_path=None, library=lib, job_id="c1", emit=lambda e: None,
                     synth_factory=Synth, chunk_cache=MemoryCache())
    assert calls == [text]  # synthesized fresh, not served from the F5-era entry
