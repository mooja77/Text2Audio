"""Background render jobs with reconnectable SSE event history."""
import asyncio
import json
import threading
import time


class JobManager:
    def __init__(self, retention_seconds: float = 3600):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._retention_seconds = retention_seconds

    def _prune(self) -> None:
        cutoff = time.monotonic() - self._retention_seconds
        stale = [job_id for job_id, state in self._jobs.items()
                 if state["complete"] and state["updated"] < cutoff]
        for job_id in stale:
            self._jobs.pop(job_id, None)

    def has(self, job_id: str) -> bool:
        with self._lock:
            self._prune()
            return job_id in self._jobs

    def submit(self, job_id: str, target) -> str:
        state = {"events": [], "complete": False, "updated": time.monotonic()}
        with self._lock:
            self._prune()
            self._jobs[job_id] = state

        def emit(event: dict) -> None:
            with self._lock:
                state["events"].append(event)
                state["updated"] = time.monotonic()

        def run() -> None:
            try:
                target(emit)
            except Exception as exc:
                emit({"type": "error", "message": str(exc)})
            finally:
                with self._lock:
                    state["complete"] = True
                    state["updated"] = time.monotonic()

        threading.Thread(target=run, daemon=True).start()
        return job_id

    def drain(self, job_id: str, timeout: float = 5.0) -> list[dict]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                state = self._jobs[job_id]
                if state["complete"]:
                    return list(state["events"])
            time.sleep(0.01)
        raise TimeoutError(f"job {job_id} did not finish")

    async def stream(self, job_id: str, request=None, after: int = 0):
        with self._lock:
            state = self._jobs.get(job_id)
        if state is None:
            yield 'data: {"type": "error", "message": "unknown job"}\n\n'
            return
        cursor = max(0, after)
        while True:
            if request is not None and await request.is_disconnected():
                break
            with self._lock:
                events = list(state["events"][cursor:])
                complete = state["complete"]
            for item in events:
                cursor += 1
                yield f"id: {cursor}\ndata: {json.dumps(item)}\n\n"
            if complete and not events:
                break
            await asyncio.sleep(0.1)
