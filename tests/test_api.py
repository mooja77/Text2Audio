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
