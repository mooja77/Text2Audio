import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("T2A_LIBRARY_DIR", str(tmp_path / "library"))
    import importlib, server
    importlib.reload(server)
    with TestClient(server.app) as c:
        yield c


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_voices_listed(client):
    r = client.get("/api/voices")
    assert r.status_code == 200
    voices = r.json()
    assert any(v["id"] == "bm_george" for v in voices)
    g = next(v for v in voices if v["id"] == "bm_george")
    assert g["accent"] == "British" and g["gender"] == "Male"


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Text2Audio" in r.text


def test_ingest_returns_chapters(client):
    files = [
        ("files", ("Chapter01_A.md", b"# Chapter 1 - Alpha\n\nFirst body.", "text/markdown")),
        ("files", ("Chapter02_B.md", b"# Chapter 2 - Beta\n\nSecond body.", "text/markdown")),
    ]
    r = client.post("/api/ingest", files=files)
    assert r.status_code == 200
    data = r.json()
    assert [c["title"] for c in data["chapters"]] == ["Chapter 1 - Alpha", "Chapter 2 - Beta"]
    assert data["chapters"][0]["chars"] > 0
    assert "bookText" in data and "## Chapter 1 - Alpha" in data["bookText"]


import json as _json
import numpy as np
from pipeline.synth import SAMPLE_RATE


class _FakeSynth:
    def __init__(self, voice, lang_code, speed=1.0):
        pass
    def synth_chunks(self, chunks, progress=None):
        return np.zeros(int(0.1 * SAMPLE_RATE), dtype=np.float32)
    def synth_paragraphs(self, paragraphs, progress=None):
        n = sum(len(p) for p in paragraphs)
        return np.zeros(int(0.1 * SAMPLE_RATE) * max(1, n), dtype=np.float32)


def test_render_job_streams_done_and_creates_library_entry(client, monkeypatch):
    import server
    monkeypatch.setattr(server, "SYNTH_FACTORY", _FakeSynth)
    book = "## Chapter 1 - One\nChapter 1. One.\n\nHello.\n\n## Chapter 2 - Two\nChapter 2. Two.\n\nBye."
    r = client.post("/api/render", json={"bookText": book, "voice": "bm_george",
                                         "speed": 0.9, "title": "Streamed", "author": "Me"})
    assert r.status_code == 200
    job_id = r.json()["jobId"]

    types = []
    with client.stream("GET", f"/api/render/{job_id}/stream") as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            ev = _json.loads(line[5:].strip())
            types.append(ev["type"])
            if ev["type"] in ("done", "error"):
                lib_id = ev.get("libraryId")
                break
    assert "progress" in types and types[-1] == "done"
    detail = client.get(f"/api/library/{lib_id}")  # added in Task 9; if 404 here, run after Task 9
    # The library entry exists on disk regardless of the detail route:
    assert server.library.get(lib_id)["title"] == "Streamed"


def _make_one(client, server, monkeypatch, title="LibBook"):
    monkeypatch.setattr(server, "SYNTH_FACTORY", _FakeSynth)
    book = "## Chapter 1 - One\nChapter 1. One.\n\nHi."
    job = client.post("/api/render", json={"bookText": book, "voice": "af_heart",
                                           "speed": 1.0, "title": title, "author": "A"}).json()["jobId"]
    with client.stream("GET", f"/api/render/{job}/stream") as resp:
        for line in resp.iter_lines():
            if line.startswith("data:") and '"done"' in line:
                break
    return job


def test_library_list_and_detail(client, monkeypatch):
    import server
    jid = _make_one(client, server, monkeypatch, "DetailBook")
    lst = client.get("/api/library").json()
    assert any(m["id"] == jid for m in lst)
    detail = client.get(f"/api/library/{jid}").json()
    assert detail["title"] == "DetailBook" and len(detail["chapters"]) == 1


def test_audio_supports_range(client, monkeypatch):
    import server
    jid = _make_one(client, server, monkeypatch)
    full = client.get(f"/api/audio/{jid}")
    assert full.status_code == 200 and int(full.headers["content-length"]) > 0
    part = client.get(f"/api/audio/{jid}", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and part.headers["content-range"].startswith("bytes 0-99/")


def test_retag_and_delete(client, monkeypatch):
    import server
    jid = _make_one(client, server, monkeypatch)
    r = client.post(f"/api/library/{jid}/retag", json={"title": "New Title", "author": "New Author"})
    assert r.status_code == 200
    assert client.get(f"/api/library/{jid}").json()["title"] == "New Title"
    assert client.delete(f"/api/library/{jid}").status_code == 200
    assert client.get(f"/api/library/{jid}").status_code == 404


def test_voice_preview_returns_wav(client, monkeypatch):
    import server
    monkeypatch.setattr(server, "SYNTH_FACTORY", _FakeSynth)
    r = client.post("/api/voice-preview", json={"voice": "bm_george"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert len(r.content) > 44  # more than a bare WAV header


def test_unknown_voice_render_returns_400(client):
    r = client.post("/api/render", json={"bookText": "## A\n\nhi", "voice": "nope"})
    assert r.status_code == 400


def test_invalid_library_id_rejected(client):
    # Non-hex ids never reach the filesystem (path-traversal defense) -> 404.
    assert client.get("/api/library/not-a-valid-id").status_code == 404
    assert client.get("/api/audio/zzzznothex").status_code == 404
    assert client.delete("/api/library/nothexid").status_code == 404


def test_second_render_rejected_while_busy(client, monkeypatch):
    import threading
    import server

    gate = threading.Event()

    class _BlockingSynth:
        def __init__(self, voice, lang_code, speed=1.0):
            pass
        def synth_chunks(self, chunks, progress=None):
            gate.wait(timeout=5)
            return np.zeros(int(0.1 * SAMPLE_RATE), dtype=np.float32)

    monkeypatch.setattr(server, "SYNTH_FACTORY", _BlockingSynth)
    book = "## Chapter 1 - One\nChapter 1. One.\n\nHi."
    r1 = client.post("/api/render", json={"bookText": book, "voice": "af_heart", "title": "A"})
    assert r1.status_code == 200
    # second render while the first holds the GPU lock -> 409
    r2 = client.post("/api/render", json={"bookText": book, "voice": "af_heart", "title": "B"})
    assert r2.status_code == 409
    gate.set()  # let the first render finish (releases the lock)
    with client.stream("GET", f"/api/render/{r1.json()['jobId']}/stream") as resp:
        for line in resp.iter_lines():
            if line.startswith("data:") and ('"done"' in line or '"error"' in line):
                break


def test_render_ignores_client_supplied_cover_path(client, monkeypatch):
    # A client-supplied filesystem path must never be read/copied by the server.
    import server
    monkeypatch.setattr(server, "SYNTH_FACTORY", _FakeSynth)
    book = "## Chapter 1 - One\nChapter 1. One.\n\nHi."
    r = client.post("/api/render", json={"bookText": book, "voice": "af_heart",
                                         "title": "NoCover", "coverPath": "C:/Windows/win.ini"})
    assert r.status_code == 200
    jid = r.json()["jobId"]
    with client.stream("GET", f"/api/render/{jid}/stream") as resp:
        for line in resp.iter_lines():
            if line.startswith("data:") and '"done"' in line:
                break
    assert server.library.get(jid)["coverFile"] is None
    assert client.get(f"/api/cover/{jid}").status_code == 404


def test_remaster_endpoint_updates_manifest(client, monkeypatch):
    import server
    jid = _make_one(client, server, monkeypatch, "RemasterMe")
    r = client.post(f"/api/library/{jid}/remaster", json={"bitrate": "96k"})
    assert r.status_code == 200
    assert r.json()["bitrate"] == "96k"
    assert client.get(f"/api/library/{jid}").json()["bitrate"] == "96k"


def test_purge_endpoint_flips_flags_and_blocks_remaster(client, monkeypatch):
    import server
    jid = _make_one(client, server, monkeypatch)
    p = client.post(f"/api/library/{jid}/purge-wav")
    assert p.status_code == 200 and p.json()["wavKept"] is False
    assert client.post(f"/api/library/{jid}/remaster").status_code == 400


def test_remaster_bad_id_404(client):
    assert client.post("/api/library/not-hex-id/remaster").status_code == 404
