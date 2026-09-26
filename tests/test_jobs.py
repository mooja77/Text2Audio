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


def test_job_can_be_cancelled_and_reports_status():
    import threading
    jm = JobManager()
    gate = threading.Event()
    jm.submit("j3", lambda emit: gate.wait(1))
    assert jm.cancel("j3") is True
    assert jm.is_cancelled("j3") is True
    assert jm.status("j3")["cancelled"] is True
    gate.set()
