"""Background render jobs with a thread-safe progress queue and SSE streaming."""
import asyncio
import json
import queue
import threading


class JobManager:
    def __init__(self):
        self._queues: dict[str, queue.Queue] = {}

    def has(self, job_id: str) -> bool:
        return job_id in self._queues

    def submit(self, job_id: str, target) -> str:
        q: queue.Queue = queue.Queue()
        self._queues[job_id] = q

        def emit(event: dict) -> None:
            q.put(event)

        def run() -> None:
            try:
                target(emit)
            except Exception as exc:  # surface failures to the UI
                q.put({"type": "error", "message": str(exc)})
            finally:
                q.put(None)  # sentinel: stream end

        threading.Thread(target=run, daemon=True).start()
        return job_id

    def drain(self, job_id: str, timeout: float = 5.0) -> list[dict]:
        """Test helper: block until the sentinel, returning all events."""
        q = self._queues[job_id]
        events = []
        while True:
            item = q.get(timeout=timeout)
            if item is None:
                break
            events.append(item)
        return events

    async def stream(self, job_id: str):
        q = self._queues.get(job_id)
        if q is None:
            yield 'data: {"type": "error", "message": "unknown job"}\n\n'
            return
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.1)
                continue
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"
