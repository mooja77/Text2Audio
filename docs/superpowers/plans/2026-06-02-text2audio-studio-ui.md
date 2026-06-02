# Text2Audio Studio UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the basic Gradio form with a polished local "audiobook studio" — a FastAPI backend serving a Studio-Dark, top-tab web UI (Create / Voices / Library) over the existing, unchanged TTS pipeline.

**Architecture:** FastAPI backend (`server.py`) wraps the proven `pipeline/` modules. New `pipeline/ingest.py` cleans Markdown/txt into book text. `backend/` holds library persistence, render orchestration, and a background job manager that streams per-chapter progress via SSE. A hand-crafted `web/` frontend (vanilla HTML/CSS/JS, no build step) consumes the API.

**Tech Stack:** Python 3.11, FastAPI 0.136 + uvicorn (already installed), the existing kokoro/torch/soundfile/ffmpeg pipeline, pytest + FastAPI TestClient (synth mocked → GPU-free tests), vanilla JS frontend.

---

## Environment notes (already done — do NOT redo)

- venv at `.venv`; use `./.venv/Scripts/python.exe`. Installed: pytest, numpy, soundfile, gradio, torch+cu124, kokoro, **fastapi[standard]** (uvicorn, httpx, python-multipart), **aiofiles**. ffmpeg 8.1 and espeak-ng 1.52 on the machine.
- Git identity: if a commit fails on identity use `git -c user.name="Text2Audio" -c user.email="mooja77@gmail.com" commit ...`.
- The existing `pipeline/parse.py`, `chunk.py`, `synth.py`, `assemble.py` and their tests are DONE and must not be modified.
- `md_to_book.py` exists at repo root; its logic is ported into `pipeline/ingest.py` in Task 1 (leave the old file in place).

## Locked interfaces (use these exact names across tasks)

- `pipeline/ingest.py`: `clean_markdown(text:str)->str`; `section_from_text(filename:str, raw:str)->tuple[str,str]` (returns `(marker_title, narrated_text)`); `build_book_text(sources:list[tuple[str,str]])->str` (sources = `(filename, content)`); `build_book_text_from_paths(paths:list[str])->str`.
- `backend/library.py`: `class Library(base_dir:str)` with `new_dir(id)->str`, `save_manifest(id, manifest:dict)->None`, `list()->list[dict]`, `get(id)->dict|None`, `audio_path(id)->str`, `cover_path(id)->str|None`, `delete(id)->None`. Module helper `new_id()->str`.
- `backend/render.py`: `render_audiobook(*, book_text, voice, speed, title, author, cover_path, library, job_id, emit, synth_factory=Synthesizer)->dict` (returns manifest).
- `backend/jobs.py`: `class JobManager` with `submit(job_id:str, target:Callable[[Callable[[dict],None]],None])->str`, `has(job_id)->bool`, `stream(job_id)->async generator[str]` (yields SSE `data:` frames).
- `server.py`: module global `SYNTH_FACTORY = Synthesizer` (tests monkeypatch it); `app` (FastAPI). Library root `LIBRARY_DIR = "library"`.
- Manifest dict keys: `id, title, author, voice, speed, created, durationSeconds, sizeBytes, chapters:[{title,startMs,endMs}], coverFile`.

## File structure

```
server.py                 # FastAPI app, routes, static serving, uvicorn launch
backend/__init__.py
backend/library.py        # library/<id>/ persistence + manifest
backend/render.py         # pipeline orchestration (parse->synth->assemble->manifest)
backend/jobs.py           # background render thread + SSE event queue
pipeline/ingest.py        # md/txt -> book text (ported from md_to_book.py)
web/index.html            # SPA shell: top-tab nav
web/css/studio.css        # Studio Dark theme
web/js/app.js             # tab routing + shared API client
web/js/create.js          # Create tab
web/js/voices.js          # Voices gallery
web/js/library.js         # Library grid + detail
web/js/player.js          # in-app chapter player
tests/test_ingest.py
tests/test_library.py
tests/test_render.py
tests/test_jobs.py
tests/test_api.py
library/                  # generated audiobooks (gitignored)
```

`library/` is already covered by `output/` patterns? No — add `library/` to `.gitignore` in Task 2.

---

## Task 1: Markdown/txt ingest module (`pipeline/ingest.py`)

**Files:** Create `pipeline/ingest.py`, `tests/test_ingest.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_ingest.py`:

```python
from pipeline.ingest import (
    clean_markdown, section_from_text, build_book_text, build_book_text_from_paths,
)
from pipeline.parse import parse_chapters


def test_clean_markdown_strips_syntax():
    md = "# Heading\n\nSome **bold** and *italic* and `code` text.\n\n---\n\n> quote\n- bullet"
    out = clean_markdown(md)
    assert "**" not in out and "*" not in out and "`" not in out
    assert "#" not in out
    assert ">" not in out
    assert "bold" in out and "italic" in out and "code" in out
    assert "bullet" in out


def test_clean_markdown_keeps_links_text_only():
    assert clean_markdown("See [the docs](http://x.com) now.") == "See the docs now."


def test_section_from_text_uses_h1_as_title():
    marker, narrated = section_from_text("Chapter01_X.md", "# Chapter 1 - Ledger Morning (Mick)\n\nHello world.")
    assert marker == "Chapter 1 - Ledger Morning"            # POV tag dropped
    assert narrated.startswith("Chapter 1. Ledger Morning.")  # spoken heading
    assert "Hello world." in narrated
    assert "#" not in narrated


def test_section_from_text_falls_back_to_filename():
    marker, narrated = section_from_text("My_Notes.txt", "Just text, no heading.")
    assert marker == "My_Notes"
    assert "Just text, no heading." in narrated


def test_build_book_text_orders_and_marks_chapters():
    sources = [
        ("a.md", "# Chapter 1 - One\n\nFirst."),
        ("b.md", "# Chapter 2 - Two\n\nSecond."),
    ]
    text = build_book_text(sources)
    chapters = parse_chapters(text)
    assert [c.title for c in chapters] == ["Chapter 1 - One", "Chapter 2 - Two"]
    assert "First." in chapters[0].text and "Second." in chapters[1].text


def test_build_book_text_from_paths(tmp_path):
    p1 = tmp_path / "c1.md"; p1.write_text("# Chapter 1 - A\n\nAlpha.", encoding="utf-8")
    p2 = tmp_path / "c2.md"; p2.write_text("# Chapter 2 - B\n\nBeta.", encoding="utf-8")
    text = build_book_text_from_paths([str(p1), str(p2)])
    chapters = parse_chapters(text)
    assert [c.title for c in chapters] == ["Chapter 1 - A", "Chapter 2 - B"]
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_ingest.py -v` → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `pipeline/ingest.py`:**

```python
"""Convert Markdown/plain-text chapter files into a single book text for
Text2Audio. Each file's first `# H1` becomes the chapter title; Markdown syntax
is stripped; a spoken "Chapter N." heading is prepended; chapters are joined with
the `## ` marker that pipeline.parse splits on."""
import os
import re

_HR = re.compile(r"^\s*([-*_]\s*){3,}$")
_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def clean_markdown(text: str) -> str:
    out = []
    for ln in text.splitlines():
        s = ln.rstrip()
        if _HR.match(s):
            out.append("")
            continue
        s = re.sub(r"<!--.*?-->", "", s)
        s = re.sub(r"^\s*>\s?", "", s)
        s = re.sub(r"^\s*#{1,6}\s*", "", s)
        s = re.sub(r"^\s*[-*+]\s+", "", s)
        s = re.sub(r"^\s*\d+\.\s+", "", s)
        s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
        s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        s = re.sub(r"__([^_]+)__", r"\1", s)
        s = re.sub(r"\*([^*]+)\*", r"\1", s)
        s = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", s)
        s = s.replace("`", "")
        out.append(s)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _marker_title(title: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()


def _spoken_heading(marker_title: str) -> str:
    spoken = marker_title.replace(" - ", ". ").replace(" – ", ". ")
    if not spoken.endswith((".", "!", "?")):
        spoken += "."
    return spoken


def section_from_text(filename: str, raw: str) -> tuple[str, str]:
    m = _H1.search(raw)
    if m:
        title = m.group(1).strip()
        raw = raw[:m.start()] + raw[m.end():]
    else:
        title = os.path.splitext(os.path.basename(filename))[0]
    marker = _marker_title(title)
    body = clean_markdown(raw)
    return marker, f"{_spoken_heading(marker)}\n\n{body}"


def build_book_text(sources: list[tuple[str, str]]) -> str:
    sections = []
    for filename, content in sources:
        marker, narrated = section_from_text(filename, content)
        sections.append(f"## {marker}\n{narrated}")
    return "\n\n".join(sections) + "\n"


def build_book_text_from_paths(paths: list[str]) -> str:
    sources = []
    for p in paths:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            sources.append((os.path.basename(p), f.read()))
    return build_book_text(sources)
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_ingest.py -v` → 6 passed.

- [ ] **Step 5: Commit** — `git add pipeline/ingest.py tests/test_ingest.py && git commit -m "feat: pipeline.ingest — markdown/txt to book text"`

---

## Task 2: Dependencies + gitignore

**Files:** Modify `requirements.txt`, `.gitignore`

- [ ] **Step 1: Append to `requirements.txt`** (after the existing lines):

```
fastapi>=0.115
uvicorn>=0.30
python-multipart>=0.0.9
aiofiles>=23.0
httpx>=0.27
```

- [ ] **Step 2: Add `library/` to `.gitignore`** — append a line `library/` to `.gitignore`.

- [ ] **Step 3: Verify deps import** — `./.venv/Scripts/python.exe -c "import fastapi, uvicorn, multipart, aiofiles, httpx; print('ok')"` → prints `ok`.

- [ ] **Step 4: Commit** — `git add requirements.txt .gitignore && git commit -m "chore: add FastAPI backend dependencies"`

---

## Task 3: Library persistence (`backend/library.py`)

**Files:** Create `backend/__init__.py`, `backend/library.py`, `tests/test_library.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_library.py`:

```python
from backend.library import Library, new_id


def test_new_id_is_unique_hex():
    a, b = new_id(), new_id()
    assert a != b and len(a) >= 6 and a.isalnum()


def test_save_and_get_and_list(tmp_path):
    lib = Library(str(tmp_path))
    lib.new_dir("book1")
    manifest = {"id": "book1", "title": "T", "author": "A", "created": "2026-01-01T00:00:00",
                "chapters": [{"title": "C1", "startMs": 0, "endMs": 1000}]}
    lib.save_manifest("book1", manifest)
    assert lib.get("book1")["title"] == "T"
    listed = lib.list()
    assert len(listed) == 1 and listed[0]["id"] == "book1"


def test_list_sorted_newest_first(tmp_path):
    lib = Library(str(tmp_path))
    for i, ts in [("old", "2026-01-01T00:00:00"), ("new", "2026-02-01T00:00:00")]:
        lib.new_dir(i); lib.save_manifest(i, {"id": i, "created": ts})
    assert [m["id"] for m in lib.list()] == ["new", "old"]


def test_get_missing_returns_none(tmp_path):
    assert Library(str(tmp_path)).get("nope") is None


def test_delete_removes_dir(tmp_path):
    lib = Library(str(tmp_path)); lib.new_dir("x"); lib.save_manifest("x", {"id": "x", "created": "2026"})
    lib.delete("x")
    assert lib.get("x") is None


def test_audio_and_cover_paths(tmp_path):
    lib = Library(str(tmp_path)); d = lib.new_dir("y")
    assert lib.audio_path("y").replace("\\", "/").endswith("y/book.m4b")
    # cover_path returns None until a cover.jpg exists
    assert lib.cover_path("y") is None
    open(lib.audio_path("y"), "wb").close()  # touch to ensure dir works
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_library.py -v` → FAIL.

- [ ] **Step 3: Create `backend/__init__.py`** with one line:

```python
"""Text2Audio backend (FastAPI server support modules)."""
```

- [ ] **Step 4: Implement `backend/library.py`:**

```python
"""Persistence for generated audiobooks under a library directory."""
import json
import os
import shutil
import uuid

AUDIO_NAME = "book.m4b"
COVER_NAME = "cover.jpg"
MANIFEST_NAME = "manifest.json"


def new_id() -> str:
    return uuid.uuid4().hex[:10]


class Library:
    def __init__(self, base_dir: str):
        self.base = base_dir
        os.makedirs(self.base, exist_ok=True)

    def _dir(self, id: str) -> str:
        return os.path.join(self.base, id)

    def new_dir(self, id: str) -> str:
        d = self._dir(id)
        os.makedirs(d, exist_ok=True)
        return d

    def save_manifest(self, id: str, manifest: dict) -> None:
        with open(os.path.join(self._dir(id), MANIFEST_NAME), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    def get(self, id: str) -> dict | None:
        path = os.path.join(self._dir(id), MANIFEST_NAME)
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list(self) -> list[dict]:
        items = []
        if os.path.isdir(self.base):
            for name in os.listdir(self.base):
                m = self.get(name)
                if m:
                    items.append(m)
        items.sort(key=lambda m: m.get("created", ""), reverse=True)
        return items

    def audio_path(self, id: str) -> str:
        return os.path.join(self._dir(id), AUDIO_NAME)

    def cover_path(self, id: str) -> str | None:
        p = os.path.join(self._dir(id), COVER_NAME)
        return p if os.path.isfile(p) else None

    def delete(self, id: str) -> None:
        shutil.rmtree(self._dir(id), ignore_errors=True)
```

- [ ] **Step 5: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_library.py -v` → 6 passed.

- [ ] **Step 6: Commit** — `git add backend/__init__.py backend/library.py tests/test_library.py && git commit -m "feat: backend.library persistence"`

---

## Task 4: Render orchestration (`backend/render.py`)

**Files:** Create `backend/render.py`, `tests/test_render.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_render.py` (uses a fake synthesizer so no GPU; ffmpeg is real):

```python
import numpy as np
from backend.library import Library
from backend.render import render_audiobook
from pipeline.synth import SAMPLE_RATE


class FakeSynth:
    def __init__(self, voice, lang_code, speed=1.0):
        self.voice = voice
    def synth_chunks(self, chunks, progress=None):
        # ~0.2s of silence per non-empty chunk list
        return np.zeros(int(0.2 * SAMPLE_RATE) * max(1, len(chunks)), dtype=np.float32)


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
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_render.py -v` → FAIL.

- [ ] **Step 3: Implement `backend/render.py`:**

```python
"""Orchestrate the TTS pipeline into a finished audiobook + manifest."""
import datetime
import os
import shutil

import numpy as np
import soundfile as sf

from pipeline.parse import parse_chapters
from pipeline.chunk import chunk_text
from pipeline.synth import Synthesizer, PRESET_VOICES, SAMPLE_RATE
from pipeline.assemble import write_wav, build_m4b


def render_audiobook(*, book_text, voice, speed, title, author, cover_path,
                     library, job_id, emit, synth_factory=Synthesizer) -> dict:
    chapters = parse_chapters(book_text, default_title=title or "Audiobook")
    workdir = library.new_dir(job_id)
    synth = synth_factory(voice=voice, lang_code=PRESET_VOICES[voice], speed=float(speed))

    n = len(chapters)
    chapter_wavs = []
    for i, ch in enumerate(chapters):
        emit({"type": "progress", "chapterIndex": i, "chapterCount": n,
              "chapterTitle": ch.title, "percent": round(i / max(1, n) * 100)})
        audio = synth.synth_chunks(chunk_text(ch.text))
        if len(audio) == 0:
            audio = np.zeros(int(0.5 * SAMPLE_RATE), dtype=np.float32)
        wp = os.path.join(workdir, f"chapter_{i + 1:03d}.wav")
        write_wav(audio, wp)
        chapter_wavs.append((ch.title, wp))

    cover_dest = None
    if cover_path:
        cover_dest = os.path.join(workdir, "cover.jpg")
        shutil.copyfile(cover_path, cover_dest)

    out = library.audio_path(job_id)
    build_m4b(chapter_wavs, out, book_title=title or None, author=author or None, cover=cover_dest)

    chapters_meta = []
    start = 0
    for ctitle, wp in chapter_wavs:
        info = sf.info(wp)
        dur = int(round(info.frames / info.samplerate * 1000))
        chapters_meta.append({"title": ctitle, "startMs": start, "endMs": start + dur})
        start += dur
    for _, wp in chapter_wavs:
        try:
            os.remove(wp)
        except OSError:
            pass

    manifest = {
        "id": job_id, "title": title or "Audiobook", "author": author or "",
        "voice": voice, "speed": float(speed),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "durationSeconds": round(start / 1000, 1), "sizeBytes": os.path.getsize(out),
        "chapters": chapters_meta, "coverFile": "cover.jpg" if cover_dest else None,
    }
    library.save_manifest(job_id, manifest)
    emit({"type": "done", "libraryId": job_id, "percent": 100})
    return manifest
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_render.py -v` → 2 passed.

- [ ] **Step 5: Commit** — `git add backend/render.py tests/test_render.py && git commit -m "feat: backend.render pipeline orchestration"`

---

## Task 5: Background job manager (`backend/jobs.py`)

**Files:** Create `backend/jobs.py`, `tests/test_jobs.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_jobs.py`:

```python
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
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_jobs.py -v` → FAIL.

- [ ] **Step 3: Implement `backend/jobs.py`:**

```python
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
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_jobs.py -v` → 2 passed.

- [ ] **Step 5: Commit** — `git add backend/jobs.py tests/test_jobs.py && git commit -m "feat: backend.jobs background render + SSE queue"`

---

## Task 6: Server core — app, health, voices, static, lifespan (`server.py`)

**Files:** Create `server.py`; create `tests/test_api.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v` → FAIL.

- [ ] **Step 3: Implement `server.py`** (this version covers Task 6; later tasks ADD routes to it — keep the static mount LAST):

```python
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
```

NOTE for later tasks: new `@app.<method>` routes must be added ABOVE the `_mount_static()` call. When a later task edits `server.py`, insert routes immediately before the `# IMPORTANT: keep this static mount...` comment.

- [ ] **Step 4: Create a placeholder `web/index.html`** so the static mount and `/` work (Task 11 replaces it):

```html
<!doctype html><html><head><meta charset="utf-8"><title>Text2Audio</title></head>
<body><h1>Text2Audio</h1></body></html>
```

- [ ] **Step 5: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v` → 3 passed.

- [ ] **Step 6: Commit** — `git add server.py tests/test_api.py web/index.html && git commit -m "feat: server core — health, voices, static, lifespan"`

---

## Task 7: Ingest endpoint (`POST /api/ingest`)

**Files:** Modify `server.py`; add tests to `tests/test_api.py`

- [ ] **Step 1: Add the failing test** to `tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py::test_ingest_returns_chapters -v` → FAIL (404).

- [ ] **Step 3: Implement** — in `server.py`, add these imports to the existing import block:

```python
from fastapi import File, UploadFile
from pipeline.ingest import build_book_text
from pipeline.parse import parse_chapters
```

Then add this route immediately BEFORE the `# IMPORTANT: keep this static mount` comment:

```python
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
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v` → all passing.

- [ ] **Step 5: Commit** — `git add server.py tests/test_api.py && git commit -m "feat: POST /api/ingest"`

---

## Task 8: Render endpoint + SSE progress

**Files:** Modify `server.py`; add tests to `tests/test_api.py`

- [ ] **Step 1: Add the failing test** to `tests/test_api.py`:

```python
import json as _json
import numpy as np
from pipeline.synth import SAMPLE_RATE


class _FakeSynth:
    def __init__(self, voice, lang_code, speed=1.0):
        pass
    def synth_chunks(self, chunks, progress=None):
        return np.zeros(int(0.1 * SAMPLE_RATE), dtype=np.float32)


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
```

NOTE: the `client.get(f"/api/library/{lib_id}")` line exercises a Task 9 route; it is fine for it to 404 until Task 9 — the final assertion uses `server.library.get(...)` directly. Leave the line in; do not assert on its status here.

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py::test_render_job_streams_done_and_creates_library_entry -v` → FAIL.

- [ ] **Step 3: Implement** — add to `server.py` imports:

```python
from fastapi import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.library import new_id
from backend.render import render_audiobook
```

Add this model near the top (after the constants) and the routes before the static mount:

```python
class RenderRequest(BaseModel):
    bookText: str
    voice: str = "af_heart"
    speed: float = 1.0
    title: str = ""
    author: str = ""
    coverPath: str | None = None
```

```python
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
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v` → all passing (the render test now streams a `done`).

- [ ] **Step 5: Commit** — `git add server.py tests/test_api.py && git commit -m "feat: POST /api/render + SSE progress stream"`

---

## Task 9: Library endpoints (list / detail / audio range / retag / delete)

**Files:** Modify `server.py`; add tests to `tests/test_api.py`

- [ ] **Step 1: Add the failing tests** to `tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -k "library or audio or retag" -v` → FAIL.

- [ ] **Step 3: Implement** — add to `server.py` imports:

```python
from fastapi import HTTPException
```

Add these routes before the static mount:

```python
@app.get("/api/library")
def library_list():
    return library.list()


@app.get("/api/library/{id}")
def library_detail(id: str):
    m = library.get(id)
    if m is None:
        raise HTTPException(status_code=404, detail="not found")
    return m


@app.get("/api/audio/{id}")
def library_audio(id: str):
    path = library.audio_path(id)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="no audio")
    return FileResponse(path, media_type="audio/mp4")  # Starlette handles Range -> 206


@app.get("/api/cover/{id}")
def library_cover(id: str):
    p = library.cover_path(id)
    if not p:
        raise HTTPException(status_code=404, detail="no cover")
    return FileResponse(p, media_type="image/jpeg")


class RetagRequest(BaseModel):
    title: str | None = None
    author: str | None = None


@app.post("/api/library/{id}/retag")
def library_retag(id: str, req: RetagRequest):
    m = library.get(id)
    if m is None:
        raise HTTPException(status_code=404, detail="not found")
    if req.title is not None:
        m["title"] = req.title
    if req.author is not None:
        m["author"] = req.author
    library.save_manifest(id, m)
    return m


@app.delete("/api/library/{id}")
def library_delete(id: str):
    if library.get(id) is None:
        raise HTTPException(status_code=404, detail="not found")
    library.delete(id)
    return {"deleted": id}
```

NOTE: retag updates the manifest metadata (what the UI/library reads). Re-embedding tags into the `.m4b` itself is out of scope for this task.

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v` → all passing.

- [ ] **Step 5: Commit** — `git add server.py tests/test_api.py && git commit -m "feat: library endpoints (list/detail/audio-range/retag/delete)"`

---

## Task 10: Voice preview endpoint (`POST /api/voice-preview`)

**Files:** Modify `server.py`; add test to `tests/test_api.py`

- [ ] **Step 1: Add the failing test** to `tests/test_api.py`:

```python
def test_voice_preview_returns_wav(client, monkeypatch):
    import server
    monkeypatch.setattr(server, "SYNTH_FACTORY", _FakeSynth)
    r = client.post("/api/voice-preview", json={"voice": "bm_george"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert len(r.content) > 44  # more than a bare WAV header
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py::test_voice_preview_returns_wav -v` → FAIL.

- [ ] **Step 3: Implement** — add to `server.py` imports:

```python
import io
import soundfile as sf
from pipeline.synth import SAMPLE_RATE
```

Add the model and route before the static mount. The fake synth in tests has no `.preview()`, so call `synth_chunks` with the sample sentence split — but to keep the real Synthesizer's nicer `preview()`, guard for it:

```python
class PreviewRequest(BaseModel):
    voice: str


_PREVIEW_TEXT = "This is a sample of the selected narrator voice."


@app.post("/api/voice-preview")
def voice_preview(req: PreviewRequest):
    if req.voice not in PRESET_VOICES:
        raise HTTPException(status_code=400, detail="unknown voice")
    synth = SYNTH_FACTORY(voice=req.voice, lang_code=PRESET_VOICES[req.voice])
    if hasattr(synth, "preview"):
        audio = synth.preview(_PREVIEW_TEXT)
    else:
        audio = synth.synth_chunks([_PREVIEW_TEXT])
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")
```

Also add `Response` to the fastapi.responses import line: `from fastapi.responses import FileResponse, StreamingResponse, Response`.

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v` → all passing.

- [ ] **Step 5: Run the FULL suite** — `./.venv/Scripts/python.exe -m pytest -q` → all passing (1 skipped GPU smoke).

- [ ] **Step 6: Commit** — `git add server.py tests/test_api.py && git commit -m "feat: POST /api/voice-preview"`

---

## Task 11: Frontend shell + Studio Dark theme (`web/index.html`, `web/css/studio.css`)

**Files:** Replace `web/index.html`; create `web/css/studio.css`. Verified by serving (not unit tests).

- [ ] **Step 1: Replace `web/index.html`:**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Text2Audio Studio</title>
  <link rel="stylesheet" href="/css/studio.css">
</head>
<body>
  <header class="topbar">
    <div class="brand">🎧 Text2Audio <span>Studio</span></div>
    <nav class="tabs">
      <button class="tab" data-tab="library">Library</button>
      <button class="tab active" data-tab="create">Create</button>
      <button class="tab" data-tab="voices">Voices</button>
    </nav>
    <div id="ffmpeg-warn" class="warn" hidden>⚠ ffmpeg not found</div>
  </header>

  <main>
    <section id="tab-create" class="tabpane active"></section>
    <section id="tab-voices" class="tabpane"></section>
    <section id="tab-library" class="tabpane"></section>
  </main>

  <script src="/js/app.js"></script>
  <script src="/js/create.js"></script>
  <script src="/js/voices.js"></script>
  <script src="/js/library.js"></script>
  <script src="/js/player.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `web/css/studio.css`** (Studio Dark theme):

```css
:root{
  --bg:#0d1117; --panel:#161b22; --panel2:#1c232d; --bd:#30363d;
  --tx:#e6edf3; --mut:#8b949e; --ac:#58a6ff; --ac2:#a371f7; --ok:#3fb950; --err:#f85149;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:14px}
.topbar{display:flex;align-items:center;gap:24px;padding:12px 20px;
  background:var(--panel);border-bottom:1px solid var(--bd);position:sticky;top:0;z-index:10}
.brand{font-weight:700;letter-spacing:.3px}
.brand span{color:var(--mut);font-weight:400}
.tabs{display:flex;gap:6px}
.tab{background:none;border:none;color:var(--mut);padding:8px 14px;border-radius:8px;
  cursor:pointer;font-size:14px}
.tab:hover{color:var(--tx)}
.tab.active{background:#1f6feb22;color:var(--ac);font-weight:600}
.warn{margin-left:auto;color:var(--err);font-size:12px}
main{max-width:1100px;margin:0 auto;padding:22px 20px}
.tabpane{display:none}
.tabpane.active{display:block}
h2{margin:0 0 4px}
.subtitle{color:var(--mut);margin:0 0 18px}
.label{font-size:10px;letter-spacing:.8px;color:var(--mut);text-transform:uppercase;margin-bottom:8px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:820px){.grid2{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--bd);border-radius:14px;padding:16px}
.dropzone{border:1.5px dashed var(--bd);border-radius:12px;padding:26px;text-align:center;
  color:var(--mut);cursor:pointer;transition:border-color .15s,background .15s}
.dropzone.drag{border-color:var(--ac);background:#1f6feb11;color:var(--tx)}
.filelist{margin-top:12px;display:flex;flex-direction:column;gap:6px}
.filerow{display:flex;align-items:center;gap:10px;background:var(--panel2);
  border:1px solid var(--bd);border-radius:9px;padding:8px 10px}
.filerow.dragging{opacity:.5}
.grip{cursor:grab;color:var(--mut)}
.filerow .nm{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.filerow .wc{color:var(--mut);font-size:12px}
.filerow .x{cursor:pointer;color:var(--mut);border:none;background:none;font-size:16px}
.filerow .x:hover{color:var(--err)}
.field{display:block;width:100%;margin-bottom:12px}
.field label{display:block;font-size:12px;color:var(--mut);margin-bottom:5px}
.field input,.field select{width:100%;background:var(--panel2);border:1px solid var(--bd);
  color:var(--tx);border-radius:8px;padding:9px 10px;font-size:14px}
input[type=range]{width:100%;accent-color:var(--ac)}
.voicepick{display:flex;gap:8px;align-items:center}
.voicepick select{flex:1}
.btn{background:var(--panel2);border:1px solid var(--bd);color:var(--tx);border-radius:9px;
  padding:9px 14px;cursor:pointer;font-size:14px}
.btn:hover{border-color:var(--ac)}
.btn.primary{background:linear-gradient(90deg,var(--ac),var(--ac2));border:none;color:#fff;
  font-weight:600;width:100%;padding:12px;font-size:15px;margin-top:8px}
.btn.primary:disabled{opacity:.55;cursor:not-allowed}
.chaplist{margin-top:10px;max-height:230px;overflow:auto}
.chapline{display:flex;gap:10px;padding:6px 8px;border-bottom:1px solid var(--bd);font-size:13px}
.chapline .ci{color:var(--mut);width:28px}
.chapline .ct{flex:1}
.chapline .cc{color:var(--mut);font-size:12px}
.progress{margin-top:14px}
.bar{height:9px;border-radius:6px;background:#21262d;overflow:hidden}
.barf{height:100%;width:0;background:linear-gradient(90deg,var(--ac),var(--ac2));transition:width .3s}
.progress .meta{display:flex;justify-content:space-between;color:var(--mut);font-size:12px;margin-top:6px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px}
.vcard{background:var(--panel);border:1px solid var(--bd);border-radius:12px;padding:14px;cursor:pointer}
.vcard:hover{border-color:var(--ac)}
.vcard.sel{border-color:var(--ac);box-shadow:0 0 0 1px var(--ac)}
.vcard .dot{width:42px;height:42px;border-radius:50%;
  background:linear-gradient(135deg,var(--ac),var(--ac2));margin-bottom:10px}
.vcard .vn{font-weight:600}
.vcard .vm{color:var(--mut);font-size:12px}
.vcard .row{display:flex;gap:8px;margin-top:10px}
.vcard .row .btn{flex:1;padding:7px;font-size:12px;text-align:center}
.libgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px}
.libcard{background:var(--panel);border:1px solid var(--bd);border-radius:12px;overflow:hidden;cursor:pointer}
.libcard:hover{border-color:var(--ac)}
.libcard .cover{height:130px;background:linear-gradient(135deg,#1f6feb33,#a371f733);
  display:flex;align-items:center;justify-content:center;font-size:34px}
.libcard .cover img{width:100%;height:100%;object-fit:cover}
.libcard .b{padding:12px}
.libcard .t{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.libcard .m{color:var(--mut);font-size:12px;margin-top:3px}
.player{background:var(--panel);border:1px solid var(--bd);border-radius:14px;padding:18px}
.player audio{width:100%;margin:12px 0}
.player .chap{padding:8px 10px;border-radius:8px;cursor:pointer;display:flex;gap:10px;font-size:13px}
.player .chap:hover{background:var(--panel2)}
.player .chap.cur{background:#1f6feb22;color:var(--ac)}
.muted{color:var(--mut)}
.backlink{background:none;border:none;color:var(--ac);cursor:pointer;padding:0;margin-bottom:12px;font-size:13px}
.toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:var(--panel2);
  border:1px solid var(--bd);padding:10px 16px;border-radius:10px;opacity:0;transition:opacity .2s}
.toast.show{opacity:1}
```

- [ ] **Step 3: Verify it serves** — start the server without opening a browser and curl it:

Run (PowerShell): `$env:T2A_NO_BROWSER=1; Start-Process -NoNewWindow ./.venv/Scripts/python.exe server.py; Start-Sleep 3; (Invoke-WebRequest http://127.0.0.1:8765/css/studio.css).StatusCode; (Invoke-WebRequest http://127.0.0.1:8765/).Content.Contains("Studio"); Get-Process python | Stop-Process`
Expected: `200` and `True`. (If port 8765 is busy, stop stray python processes first.)

- [ ] **Step 4: Commit** — `git add web/index.html web/css/studio.css && git commit -m "feat: studio-dark shell + theme"`

---

## Task 12: Frontend core — tabs + API client (`web/js/app.js`)

**Files:** Create `web/js/app.js`. Verified manually.

- [ ] **Step 1: Implement `web/js/app.js`:**

```js
// Shared state, API helpers, tab routing.
const T2A = {
  state: { voices: [], files: [], bookText: "", chapters: [], voice: "af_heart", speed: 0.9 },
  async api(path, opts) {
    const r = await fetch(path, opts);
    if (!r.ok) throw new Error((await r.text()) || r.status);
    return r.headers.get("content-type")?.includes("application/json") ? r.json() : r;
  },
  toast(msg) {
    let t = document.querySelector(".toast");
    if (!t) { t = document.createElement("div"); t.className = "toast"; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add("show");
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2200);
  },
  showTab(name) {
    document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
    document.querySelectorAll(".tabpane").forEach(p => p.classList.toggle("active", p.id === "tab-" + name));
    if (name === "voices") Voices.render();
    if (name === "library") Library.render();
    if (name === "create") Create.render();
  },
};

window.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".tab").forEach(b => b.onclick = () => T2A.showTab(b.dataset.tab));
  try {
    const health = await T2A.api("/api/health");
    if (!health.ffmpeg) document.getElementById("ffmpeg-warn").hidden = false;
    T2A.state.voices = await T2A.api("/api/voices");
  } catch (e) { T2A.toast("Backend not reachable"); }
  Create.render();
});
```

- [ ] **Step 2: Manual check** — after Task 13–15 exist, loading `/` shows tabs that switch. For now, verify no console error: start server (`$env:T2A_NO_BROWSER=1`), open `http://127.0.0.1:8765`, confirm the three tab buttons render and clicking them toggles the active class (Create/Voices/Library panes are filled by later tasks). Stop the server.

- [ ] **Step 3: Commit** — `git add web/js/app.js && git commit -m "feat: frontend core (tabs + api client)"`

---

## Task 13: Create tab (`web/js/create.js`)

**Files:** Create `web/js/create.js`. Verified manually + via the controller's Playwright pass in Task 16.

- [ ] **Step 1: Implement `web/js/create.js`:**

```js
const Create = {
  render() {
    const el = document.getElementById("tab-create");
    const voiceOpts = T2A.state.voices.map(v =>
      `<option value="${v.id}" ${v.id === T2A.state.voice ? "selected" : ""}>${v.label} · ${v.accent} ${v.gender}</option>`).join("");
    el.innerHTML = `
      <h2>Create audiobook</h2>
      <p class="subtitle">Drop in your chapter files (.md or .txt), set options, and generate.</p>
      <div class="grid2">
        <div class="panel">
          <div class="label">Source files</div>
          <div class="dropzone" id="dz">Drop .md / .txt files here, or click to browse
            <input type="file" id="fi" multiple accept=".md,.txt" hidden></div>
          <div class="filelist" id="fl"></div>
        </div>
        <div class="panel">
          <div class="label">Settings</div>
          <div class="field"><label>Title</label><input id="f-title" placeholder="My Book"></div>
          <div class="field"><label>Author</label><input id="f-author" placeholder="Author name"></div>
          <div class="field"><label>Narrator voice</label>
            <div class="voicepick"><select id="f-voice">${voiceOpts}</select>
              <button class="btn" id="f-prev">▶ Preview</button></div></div>
          <div class="field"><label>Speed · <span id="spd">${T2A.state.speed}</span>×</label>
            <input type="range" id="f-speed" min="0.5" max="1.5" step="0.05" value="${T2A.state.speed}"></div>
          <button class="btn primary" id="gen" disabled>Generate Audiobook</button>
          <div class="progress" id="prog" hidden>
            <div class="bar"><div class="barf" id="barf"></div></div>
            <div class="meta"><span id="pmsg">Starting…</span><span id="ppct">0%</span></div>
          </div>
        </div>
      </div>
      <div class="panel" style="margin-top:20px">
        <div class="label">Detected chapters <span id="chcount" class="muted"></span></div>
        <div class="chaplist" id="chaps"><span class="muted">Add files to see chapters.</span></div>
      </div>`;
    this.bind();
  },

  bind() {
    const dz = document.getElementById("dz"), fi = document.getElementById("fi");
    dz.onclick = () => fi.click();
    fi.onchange = () => this.addFiles([...fi.files]);
    dz.ondragover = e => { e.preventDefault(); dz.classList.add("drag"); };
    dz.ondragleave = () => dz.classList.remove("drag");
    dz.ondrop = e => { e.preventDefault(); dz.classList.remove("drag"); this.addFiles([...e.dataTransfer.files]); };
    document.getElementById("f-voice").onchange = e => T2A.state.voice = e.target.value;
    document.getElementById("f-speed").oninput = e => {
      T2A.state.speed = parseFloat(e.target.value); document.getElementById("spd").textContent = e.target.value; };
    document.getElementById("f-prev").onclick = () => this.preview();
    document.getElementById("gen").onclick = () => this.generate();
    this.renderFiles();
  },

  addFiles(fileList) {
    const wanted = fileList.filter(f => /\.(md|txt)$/i.test(f.name));
    T2A.state.files.push(...wanted);
    T2A.state.files.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    this.renderFiles(); this.refreshChapters();
  },

  renderFiles() {
    const fl = document.getElementById("fl");
    fl.innerHTML = T2A.state.files.map((f, i) =>
      `<div class="filerow" draggable="true" data-i="${i}">
         <span class="grip">⋮⋮</span><span class="nm">${f.name}</span>
         <span class="wc">${Math.round(f.size / 6)}w</span>
         <button class="x" data-x="${i}">✕</button></div>`).join("");
    fl.querySelectorAll(".x").forEach(b => b.onclick = () => {
      T2A.state.files.splice(+b.dataset.x, 1); this.renderFiles(); this.refreshChapters(); });
    this.enableReorder(fl);
    document.getElementById("gen").disabled = T2A.state.files.length === 0;
  },

  enableReorder(fl) {
    let dragI = null;
    fl.querySelectorAll(".filerow").forEach(row => {
      row.ondragstart = () => { dragI = +row.dataset.i; row.classList.add("dragging"); };
      row.ondragend = () => row.classList.remove("dragging");
      row.ondragover = e => e.preventDefault();
      row.ondrop = e => {
        e.preventDefault(); const dropI = +row.dataset.i;
        const arr = T2A.state.files; const [m] = arr.splice(dragI, 1); arr.splice(dropI, 0, m);
        this.renderFiles(); this.refreshChapters();
      };
    });
  },

  async refreshChapters() {
    const chaps = document.getElementById("chaps");
    if (!T2A.state.files.length) { chaps.innerHTML = `<span class="muted">Add files to see chapters.</span>`;
      T2A.state.chapters = []; document.getElementById("chcount").textContent = ""; return; }
    const fd = new FormData();
    T2A.state.files.forEach(f => fd.append("files", f));
    try {
      const data = await T2A.api("/api/ingest", { method: "POST", body: fd });
      T2A.state.bookText = data.bookText; T2A.state.chapters = data.chapters;
      document.getElementById("chcount").textContent = `· ${data.chapters.length}`;
      chaps.innerHTML = data.chapters.map(c =>
        `<div class="chapline"><span class="ci">${c.index + 1}</span>
         <span class="ct">${c.title}</span><span class="cc">${c.chars.toLocaleString()} chars</span></div>`).join("");
    } catch (e) { T2A.toast("Ingest failed"); }
  },

  async preview() {
    const btn = document.getElementById("f-prev"); btn.textContent = "…";
    try {
      const r = await fetch("/api/voice-preview", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice: T2A.state.voice }) });
      const blob = await r.blob(); new Audio(URL.createObjectURL(blob)).play();
    } catch (e) { T2A.toast("Preview failed"); }
    btn.textContent = "▶ Preview";
  },

  async generate() {
    if (!T2A.state.bookText) { await this.refreshChapters(); }
    const gen = document.getElementById("gen"); gen.disabled = true;
    const prog = document.getElementById("prog"); prog.hidden = false;
    const body = {
      bookText: T2A.state.bookText, voice: T2A.state.voice, speed: T2A.state.speed,
      title: document.getElementById("f-title").value, author: document.getElementById("f-author").value };
    let jobId;
    try {
      const res = await T2A.api("/api/render", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      jobId = res.jobId;
    } catch (e) { T2A.toast("Could not start render"); gen.disabled = false; return; }

    const t0 = Date.now();
    const src = new EventSource(`/api/render/${jobId}/stream`);
    src.onmessage = ev => {
      const e = JSON.parse(ev.data);
      if (e.type === "progress") {
        document.getElementById("barf").style.width = e.percent + "%";
        document.getElementById("ppct").textContent = e.percent + "%";
        const el = (Date.now() - t0) / 1000;
        const eta = e.percent > 0 ? Math.round(el / e.percent * (100 - e.percent)) : 0;
        document.getElementById("pmsg").textContent =
          `Chapter ${e.chapterIndex + 1} of ${e.chapterCount} · ${e.chapterTitle} — ETA ${eta}s`;
      } else if (e.type === "done") {
        document.getElementById("barf").style.width = "100%";
        document.getElementById("ppct").textContent = "100%";
        document.getElementById("pmsg").textContent = "Done ✓";
        src.close(); gen.disabled = false; T2A.toast("Audiobook ready"); T2A.showTab("library");
      } else if (e.type === "error") {
        document.getElementById("pmsg").textContent = "Error: " + (e.message || "render failed");
        src.close(); gen.disabled = false;
      }
    };
    src.onerror = () => { src.close(); gen.disabled = false; };
  },
};
```

- [ ] **Step 2: Manual check** — covered by Task 16 (Playwright walkthrough). No commit-blocking manual step here beyond "no JS syntax error" — verify by loading `/` with the server running and confirming the Create tab renders the dropzone + settings without console errors.

- [ ] **Step 3: Commit** — `git add web/js/create.js && git commit -m "feat: Create tab (import, reorder, ingest preview, generate + SSE)"`

---

## Task 14: Voices gallery (`web/js/voices.js`)

**Files:** Create `web/js/voices.js`. Verified manually + Task 16.

- [ ] **Step 1: Implement `web/js/voices.js`:**

```js
const Voices = {
  render() {
    const el = document.getElementById("tab-voices");
    el.innerHTML = `
      <h2>Voices</h2>
      <p class="subtitle">Click a voice to hear a sample, then "Use" it in Create.</p>
      <div class="cards" id="vcards">${T2A.state.voices.map(v => `
        <div class="vcard ${v.id === T2A.state.voice ? "sel" : ""}" data-v="${v.id}">
          <div class="dot"></div>
          <div class="vn">${v.label}</div>
          <div class="vm">${v.accent} · ${v.gender}</div>
          <div class="row">
            <button class="btn play" data-v="${v.id}">▶ Sample</button>
            <button class="btn use" data-v="${v.id}">Use</button>
          </div>
        </div>`).join("")}</div>`;
    el.querySelectorAll(".play").forEach(b => b.onclick = e => { e.stopPropagation(); this.sample(b.dataset.v, b); });
    el.querySelectorAll(".use").forEach(b => b.onclick = e => {
      e.stopPropagation(); T2A.state.voice = b.dataset.v; T2A.toast("Voice set: " + b.dataset.v);
      this.render(); });
  },
  async sample(voice, btn) {
    const old = btn.textContent; btn.textContent = "…";
    try {
      const r = await fetch("/api/voice-preview", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ voice }) });
      const blob = await r.blob(); new Audio(URL.createObjectURL(blob)).play();
    } catch (e) { T2A.toast("Sample failed"); }
    btn.textContent = old;
  },
};
```

- [ ] **Step 2: Commit** — `git add web/js/voices.js && git commit -m "feat: Voices gallery + audition"`

---

## Task 15: Library grid + player (`web/js/library.js`, `web/js/player.js`)

**Files:** Create `web/js/library.js`, `web/js/player.js`. Verified manually + Task 16.

- [ ] **Step 1: Implement `web/js/player.js`:**

```js
const Player = {
  mount(container, item) {
    container.innerHTML = `
      <div class="player">
        <div style="font-weight:600;font-size:16px">${item.title}</div>
        <div class="muted" style="font-size:13px">${item.author || ""} · ${item.chapters.length} chapters</div>
        <audio id="aud" controls preload="metadata" src="/api/audio/${item.id}"></audio>
        <div class="label">Chapters</div>
        <div id="chaps"></div>
      </div>`;
    const aud = container.querySelector("#aud");
    const chaps = container.querySelector("#chaps");
    chaps.innerHTML = item.chapters.map((c, i) =>
      `<div class="chap" data-s="${c.startMs / 1000}" data-i="${i}">
         <span class="muted">${i + 1}</span><span style="flex:1">${c.title}</span>
         <span class="muted">${fmt(c.startMs / 1000)}</span></div>`).join("");
    chaps.querySelectorAll(".chap").forEach(row => row.onclick = () => {
      aud.currentTime = parseFloat(row.dataset.s); aud.play(); });
    aud.ontimeupdate = () => {
      const t = aud.currentTime * 1000;
      let cur = 0; item.chapters.forEach((c, i) => { if (t >= c.startMs) cur = i; });
      chaps.querySelectorAll(".chap").forEach(r => r.classList.toggle("cur", +r.dataset.i === cur));
    };
    function fmt(s) { const m = Math.floor(s / 60), ss = Math.floor(s % 60); return `${m}:${String(ss).padStart(2, "0")}`; }
  },
};
```

- [ ] **Step 2: Implement `web/js/library.js`:**

```js
const Library = {
  async render() {
    const el = document.getElementById("tab-library");
    el.innerHTML = `<h2>Library</h2><p class="subtitle">Your finished audiobooks.</p><div id="libwrap"></div>`;
    const wrap = document.getElementById("libwrap");
    let items;
    try { items = await T2A.api("/api/library"); }
    catch (e) { wrap.innerHTML = `<p class="muted">Could not load library.</p>`; return; }
    if (!items.length) { wrap.innerHTML = `<p class="muted">No audiobooks yet — create one in the Create tab.</p>`; return; }
    wrap.innerHTML = `<div class="libgrid">${items.map(m => `
      <div class="libcard" data-id="${m.id}">
        <div class="cover">${m.coverFile ? `<img src="/api/cover/${m.id}">` : "🎧"}</div>
        <div class="b"><div class="t">${m.title}</div>
          <div class="m">${m.author || "—"}</div>
          <div class="m">${fmtDur(m.durationSeconds)} · ${m.chapters.length} ch</div></div>
      </div>`).join("")}</div>`;
    wrap.querySelectorAll(".libcard").forEach(c => c.onclick = () => this.detail(c.dataset.id));
    function fmtDur(s) { const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60); return h ? `${h}h ${m}m` : `${m}m`; }
  },

  async detail(id) {
    const el = document.getElementById("tab-library");
    let item;
    try { item = await T2A.api(`/api/library/${id}`); } catch (e) { T2A.toast("Not found"); return; }
    el.innerHTML = `<button class="backlink" id="back">← Library</button>
      <div id="playerwrap"></div>
      <div style="margin-top:16px;display:flex;gap:8px">
        <button class="btn" id="retag">Retag</button>
        <button class="btn" id="del">Delete</button></div>`;
    document.getElementById("back").onclick = () => this.render();
    Player.mount(document.getElementById("playerwrap"), item);
    document.getElementById("del").onclick = async () => {
      if (!confirm("Delete this audiobook?")) return;
      await T2A.api(`/api/library/${id}`, { method: "DELETE" }); T2A.toast("Deleted"); this.render(); };
    document.getElementById("retag").onclick = async () => {
      const title = prompt("Title", item.title); if (title === null) return;
      const author = prompt("Author", item.author || ""); if (author === null) return;
      await T2A.api(`/api/library/${id}/retag`, { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, author }) });
      T2A.toast("Updated"); this.detail(id); };
  },
};
```

- [ ] **Step 3: Commit** — `git add web/js/library.js web/js/player.js && git commit -m "feat: Library grid + in-app chapter player"`

---

## Task 16: End-to-end verification + README

**Files:** Modify `README.md`. Controller runs a real browser pass (Playwright MCP) — no GPU needed because the smoke uses a tiny render.

- [ ] **Step 1: Full backend suite** — `./.venv/Scripts/python.exe -m pytest -q` → all pass (1 skipped GPU smoke). Fix anything red before continuing.

- [ ] **Step 2: Launch the real app** (with the real GPU pipeline) for a live check:

Run (PowerShell, background): `$env:T2A_NO_BROWSER=1; $env:PHONEMIZER_ESPEAK_LIBRARY="C:\Program Files\eSpeak NG\libespeak-ng.dll"; $env:PHONEMIZER_ESPEAK_PATH="C:\Program Files\eSpeak NG\espeak-ng.exe"; ./.venv/Scripts/python.exe server.py`
Then drive `http://127.0.0.1:8765` with the Playwright MCP tools (the controller does this, not a subagent):
  - Create tab renders; upload `samples/sample_book.txt`; detected chapters appears.
  - Voices tab renders all 15 cards.
  - Generate the sample; SSE progress advances to Done; app switches to Library.
  - Library shows the new book; open it; the player loads and a chapter click seeks.
Stop the server process when done.

- [ ] **Step 3: Update `README.md`** — replace the "## Run" section body with:

```markdown
## Run (Studio UI)

```powershell
.\.venv\Scripts\python.exe server.py
```

Opens the Text2Audio Studio in your browser. **Create** tab: drag in `.md`/`.txt`
chapter files (Markdown is auto-cleaned), set title/voice/speed, and Generate —
live per-chapter progress streams as it renders. **Voices** tab: audition any
narrator. **Library** tab: every finished audiobook with an in-app chapter player,
retag, and delete.

The classic single-screen Gradio UI is still available via `python app.py`.
```

- [ ] **Step 4: Commit** — `git add README.md && git commit -m "docs: Studio UI run instructions"`

---

## Self-review notes (addressed)

- **Spec coverage:** ingest (T1), deps/gitignore (T2), library persistence (T3), render orchestration incl. empty-chapter silence (T4), background job + SSE (T5), server core/voices/static/lifespan ffmpeg check (T6), ingest endpoint (T7), render + SSE endpoints (T8), library list/detail/audio-range/retag/delete + cover (T9), voice-preview (T10), Studio-Dark shell+theme (T11), tabs+API client (T12), Create tab with multi-file import/reorder/preview/progress (T13), Voices gallery (T14), Library grid + player with chapter seek (T15), e2e verification + README (T16). All spec sections map to a task.
- **Type/interface consistency:** `Library(base_dir)` methods, `render_audiobook(...)` kwargs, `JobManager.submit/has/stream/drain`, `SYNTH_FACTORY` monkeypatch hook, manifest keys, and the SSE event shape (`type/chapterIndex/chapterCount/chapterTitle/percent/libraryId`) are used identically across backend tasks and the frontend (`create.js` reads exactly those event fields; `library.js`/`player.js` read exactly the manifest keys).
- **GPU-free tests:** every pytest task mocks synthesis (`FakeSynth`/`_FakeSynth`) or avoids it; ffmpeg is real and available; the only GPU test remains the opt-in `RUN_KOKORO` smoke from the original suite.
- **No placeholders:** every code/test step is complete and runnable. The one intentional cross-task note (Task 8's `/api/library/{id}` line exercised before Task 9) is called out explicitly and does not gate the assertion.
- **Out of scope (per spec):** voice cloning, EPUB/PDF import, desktop packaging, re-embedding tags into the m4b on retag.
```
