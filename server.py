"""Text2Audio Studio — FastAPI backend serving the web UI over the TTS pipeline."""
import os
import shutil
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pipeline.synth import Synthesizer, PRESET_VOICES
from backend.library import Library
from backend.jobs import JobManager

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
