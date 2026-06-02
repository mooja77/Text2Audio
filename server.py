"""Text2Audio Studio — FastAPI backend serving the web UI over the TTS pipeline."""
import os
import shutil
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pipeline.synth import Synthesizer, PRESET_VOICES
from backend.library import Library, new_id
from backend.jobs import JobManager
from backend.render import render_audiobook
from pipeline.ingest import build_book_text
from pipeline.parse import parse_chapters

ROOT = Path(__file__).parent
WEB_DIR = ROOT / "web"
LIBRARY_DIR = os.environ.get("T2A_LIBRARY_DIR", str(ROOT / "library"))

SYNTH_FACTORY = Synthesizer          # tests monkeypatch this
library = Library(LIBRARY_DIR)
jobs = JobManager()

_ACCENT = {"a": "American", "b": "British"}
_VOICE_LABELS = {"af_heart": "Heart", "af_bella": "Bella", "af_nicole": "Nicole",
                 "af_sarah": "Sarah", "af_sky": "Sky", "am_michael": "Michael",
                 "am_adam": "Adam", "am_echo": "Echo", "am_liam": "Liam",
                 "bf_emma": "Emma", "bf_isabella": "Isabella", "bf_alice": "Alice",
                 "bm_george": "George", "bm_lewis": "Lewis", "bm_daniel": "Daniel"}


class RenderRequest(BaseModel):
    bookText: str
    voice: str = "af_heart"
    speed: float = 1.0
    title: str = ""
    author: str = ""
    coverPath: str | None = None


def voices_payload() -> list[dict]:
    out = []
    for vid, lang in PRESET_VOICES.items():
        out.append({"id": vid, "label": _VOICE_LABELS.get(vid, vid),
                    "accent": _ACCENT.get(lang, lang),
                    "gender": "Female" if vid[1] == "f" else "Male"})
    return out


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ffmpeg_ok = shutil.which("ffmpeg") is not None
    if not app.state.ffmpeg_ok:
        print("WARNING: ffmpeg not found on PATH — audio assembly will fail.", file=sys.stderr)
    yield


app = FastAPI(title="Text2Audio Studio", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok", "ffmpeg": shutil.which("ffmpeg") is not None}


@app.get("/api/voices")
def get_voices():
    return voices_payload()


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.post("/api/ingest")
async def ingest(files: list[UploadFile] = File(...)):
    sources = []
    for f in files:
        raw = (await f.read()).decode("utf-8", errors="replace")
        sources.append((f.filename or "untitled.txt", raw))
    book_text = build_book_text(sources)
    chapters = parse_chapters(book_text)
    return {
        "bookText": book_text,
        "chapters": [{"index": i, "title": c.title, "chars": len(c.text)}
                     for i, c in enumerate(chapters)],
    }


@app.post("/api/render")
def start_render(req: RenderRequest):
    if req.voice not in PRESET_VOICES:
        return {"error": "unknown voice"}
    job_id = new_id()

    def target(emit):
        render_audiobook(book_text=req.bookText, voice=req.voice, speed=req.speed,
                         title=req.title, author=req.author, cover_path=req.coverPath,
                         library=library, job_id=job_id, emit=emit,
                         synth_factory=SYNTH_FACTORY)

    jobs.submit(job_id, target)
    return {"jobId": job_id}


@app.get("/api/render/{job_id}/stream")
async def render_stream(job_id: str):
    return StreamingResponse(jobs.stream(job_id), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# IMPORTANT: keep this static mount as the LAST route registration in the file.
def _mount_static():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


_mount_static()


if __name__ == "__main__":
    import uvicorn
    host, port = "127.0.0.1", 8765
    if os.environ.get("T2A_NO_BROWSER") != "1":
        threading.Timer(0.8, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(app, host=host, port=port, log_level="info")
