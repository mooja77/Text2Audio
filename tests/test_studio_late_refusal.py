"""Late studio refusal (load or inference): fatal, no retry, own cleanup, actionable API/SSE."""
from tests.server_isolation import assert_server_owned_paths
import importlib
import io
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

import pipeline.clone_synth as cs
from backend import device_fallback as df
from backend.firstrun import friendly_error
from pipeline import engine_worker
from pipeline.synth import BaseSynthesizer, ChunkSynthError, FatalSynthError


def test_studio_unavailable_is_fatal_and_not_retried():
    class S(BaseSynthesizer):
        calls = 0

        def synth_chunk(self, text):
            S.calls += 1
            raise df.StudioUnavailable(df.OOM_STUDIO)

    assert issubclass(df.StudioUnavailable, FatalSynthError)
    with pytest.raises(df.StudioUnavailable):
        S().synth_chunk_with_retry("x")
    assert S.calls == 1


def test_ordinary_error_still_retried_once():
    class S(BaseSynthesizer):
        calls = 0

        def synth_chunk(self, text):
            S.calls += 1
            raise RuntimeError("flaky")

    with pytest.raises(ChunkSynthError):
        S().synth_chunk_with_retry("x")
    assert S.calls == 2


class OOMEngine:
    def __init__(self):
        self.calls = 0

    def synth(self, text, voice=None, ref=None, ref_text=""):
        self.calls += 1
        raise RuntimeError("CUDA out of memory. Tried to allocate 2 GiB")


def test_worker_inference_oom_returns_structured_unavailable_and_stops():
    eng, out = OOMEngine(), io.StringIO()
    lines = "".join(json.dumps(r) + "\n" for r in [{"text": "a"}, {"text": "b"}])
    engine_worker.serve(eng, io.StringIO(lines), out)
    replies = [json.loads(x) for x in out.getvalue().splitlines()]
    assert replies[0] == {"ready": True}
    assert replies[1] == {"unavailable": df.OOM_STUDIO_INFERENCE}
    assert len(replies) == 2 and eng.calls == 1


class FakeProc:
    def __init__(self, reply):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(json.dumps(reply) + "\n")
        self.killed = False

    def poll(self):
        return 0 if self.killed else None

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return 0


def test_parent_raises_fatal_without_retry_and_reaps_only_own_worker():
    proc, other = FakeProc({"unavailable": df.OOM_STUDIO_INFERENCE}), FakeProc({})
    s = cs.NeuralSynthesizer.__new__(cs.NeuralSynthesizer)
    s.voice, s.ref_wav, s.ref_text, s.speed, s._proc = "studio_narrator", None, "", 1.0, proc
    with pytest.raises(df.StudioUnavailable, match="ran out of memory"):
        s.synth_chunk_with_retry("hello")
    assert proc.killed and not other.killed
    assert len(proc.stdin.getvalue().splitlines()) == 1  # one request: no retry


def test_friendly_error_preserves_typed_reason_without_reinstall_advice():
    msg = friendly_error(df.StudioUnavailable(df.OOM_STUDIO_INFERENCE))
    assert msg == df.OOM_STUDIO_INFERENCE
    assert "Install" not in msg and "reinstall" not in msg.lower()
    assert friendly_error(RuntimeError("boom")) != df.OOM_STUDIO_INFERENCE


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("T2A_LIBRARY_DIR", str(tmp_path / "library"))
    import server
    importlib.reload(server)
    assert_server_owned_paths(server, tmp_path)
    # Initial GPU precheck passes; the refusal only happens late, in the factory.
    monkeypatch.setattr(server, "device_decision", lambda: server.DeviceDecision("cuda", True, ""))

    def refuse(voice, speed):
        raise df.StudioUnavailable(df.OOM_STUDIO)
    monkeypatch.setattr(server, "SYNTH_FACTORY", refuse)
    with TestClient(server.app) as c:
        yield c


def test_preview_late_refusal_is_409_with_plain_reason(client):
    r = client.post("/api/voice-preview", json={"voice": "studio_narrator"})
    assert r.status_code == 409
    assert r.json() == {"detail": df.OOM_STUDIO, "error": "studio_unavailable",
                        "voice": "studio_narrator"}
    import server
    assert server._render_lock.acquire(blocking=False)  # lock was released
    server._render_lock.release()


def test_background_render_sse_error_keeps_typed_reason(client):
    import server
    r = client.post("/api/render", json={"bookText": "## A\n\nhi", "voice": "studio_narrator"})
    assert r.status_code == 200
    events = server.jobs.drain(r.json()["jobId"], timeout=5)
    err = events[-1]
    assert err["type"] == "error" and err["friendly"] == df.OOM_STUDIO
    assert "Install" not in err["friendly"]
    assert server.library.list() == []  # no partial book, no narrator substitution
