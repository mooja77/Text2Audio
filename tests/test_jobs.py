import time
from backend.jobs import JobManager


def test_submit_runs_target_and_collects_events():
    jm = JobManager()
    def target(emit):
        emit({"type": "progress", "percent": 50})
        emit({"type": "done", "percent": 100})
    jm.submit("j1", target)
    assert jm.has("j1")
    # drain the internal queue (test helper)
    events = jm.drain("j1", timeout=2.0)
    assert {e["type"] for e in events} == {"progress", "done"}


def test_target_exception_emits_error():
    jm = JobManager()
    def target(emit):
        raise RuntimeError("boom")
    jm.submit("j2", target)
    events = jm.drain("j2", timeout=2.0)
    assert events[-1]["type"] == "error" and "boom" in events[-1]["message"]
