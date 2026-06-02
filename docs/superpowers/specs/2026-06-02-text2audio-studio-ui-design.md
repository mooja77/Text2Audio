# Text2Audio Studio — Top-Class UI/UX Design

**Date:** 2026-06-02
**Status:** Approved design, ready for implementation planning
**Supersedes the UI of:** the original Gradio `app.py` (the pipeline is reused unchanged)

## Goal

Replace the basic Gradio form with a polished, local **audiobook studio**: a
custom web UI on a small FastAPI backend that wraps the existing, tested Python
pipeline. Fully local and free; launches with one command.

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Technology | Custom local web app — FastAPI backend + hand-crafted HTML/CSS/JS frontend (no JS build toolchain) |
| Visual style | **Studio Dark** (sleek, focused, music-app energy; accents `#58a6ff`→`#a371f7`) |
| Navigation | **Top tabs**: Library · Create · Voices |
| Premium features | All four: multi-file import + reorder, built-in player, voice audition gallery, library of past renders |
| Pipeline | Reused unchanged (`parse`, `chunk`, `synth`, `assemble`); Markdown cleaning folded into a new `pipeline/ingest.py` |

## Architecture

```
Browser UI (web/)  — Studio-Dark, top-tab nav, vanilla HTML/CSS/JS
        │  REST + SSE (localhost only)
FastAPI backend (server.py)
        │  calls (unchanged)
pipeline/  parse · chunk · synth · assemble   +   pipeline/ingest.py (new)
```

**Principles:**
- No Node/JS build step — the frontend is plain HTML/CSS/JS served by FastAPI, so
  startup stays `python server.py` (opens the browser).
- Renders run as a background job; per-chapter progress streams to the UI via SSE.
- Each finished audiobook is persisted under `library/<id>/` and the UI reads from there.
- The pipeline modules and their tests are not modified.

## New file structure

```
server.py                 # FastAPI app, route wiring, static serving, browser launch
backend/
  __init__.py
  jobs.py                 # background render job manager + progress event bus
  library.py              # library/ read·write + manifest schema/dataclass
pipeline/ingest.py        # files (.md/.txt) -> book text + ordered chapters (from md_to_book.py)
web/
  index.html              # shell: top-tab nav + tab containers
  css/studio.css          # Studio Dark theme
  js/app.js               # tab routing, shared state, API client
  js/create.js            # Create tab: import, reorder, settings, generate, progress
  js/voices.js            # Voices gallery + audition
  js/library.js           # Library grid + detail
  js/player.js            # in-app chapter player (HTML5 audio + range streaming)
tests/
  test_ingest.py          # Markdown clean / title derivation / ordering
  test_api.py             # FastAPI TestClient routes with synth mocked
library/                  # generated audiobooks (gitignored)
```

The existing Gradio `app.py` is retained as a minimal fallback launcher but is no
longer the primary UI. `md_to_book.py`'s logic moves into `pipeline/ingest.py`
(the standalone script may remain as a thin CLI wrapper around it).

## Components (screens)

### ① Create tab (main workspace)
- **Left — Source:** drag-and-drop import zone; a reorderable list of files. Each
  row shows derived chapter title + word count, a drag grip, and a remove (✕).
  Markdown is cleaned on import via `ingest`.
- **Right — Settings:** Title, Author, Cover (image drop), Voice (dropdown/quick
  pick with a ▶ audition button), Speed slider (0.5–1.5), and an advanced
  collapsed field for the chapter-marker prefix.
- **Detected Chapters preview:** list of `# · Title · chars` so the split is
  confirmed before rendering.
- **Generate Audiobook** button → on click, the area becomes a live progress
  panel: overall %, "Chapter X of Y · <title>", elapsed + ETA, streamed per chapter.

### ② Voices tab
- Gallery of narrator cards (accent + gender from `PRESET_VOICES`). Click plays a
  cached sample sentence. "Use this voice" sets the Create tab's voice.

### ③ Library tab
- Grid of finished audiobooks: cover, title, author, duration, chapter count, date.
  Click → detail view.

### ④ Player (inside Library detail)
- HTML5 audio with a clickable chapter list (seek to chapter), scrub bar,
  play/pause, speed. Actions: Open file location, Re-render, Retag metadata, Delete.

## API (localhost only)

| Method · Path | Purpose |
|---|---|
| `GET /api/voices` | narrator voices: id, label, accent, gender |
| `POST /api/voice-preview` | cached sample clip for a given voice |
| `POST /api/ingest` | upload files → cleaned text + detected chapters preview |
| `POST /api/render` | start a render job → `{job_id}` |
| `GET /api/render/{job_id}/stream` | **SSE**: progress events (chapter x/y, %, ETA, done, error) |
| `GET /api/library` | list audiobooks (manifest summaries) |
| `GET /api/library/{id}` | one audiobook + manifest + chapter list |
| `GET /api/audio/{id}` | stream `.m4b` with HTTP **range** support (player seek/scrub) |
| `POST /api/library/{id}/retag` | update title/author/cover (ffmpeg remux, no re-render) |
| `DELETE /api/library/{id}` | remove an audiobook |

**SSE event shape:** `{type: "progress"|"done"|"error", chapterIndex, chapterCount, chapterTitle, percent, etaSeconds, libraryId?, message?}`.

## Data flow (render)

1. Files uploaded → `ingest` strips Markdown, derives chapter titles, builds the
   book text and ordered chapter list.
2. `POST /api/render` creates a `library/<id>/` workspace and spawns a background
   worker (`backend/jobs.py`); the UI subscribes to the SSE stream.
3. Worker loops chapters: `chunk` → `synth.synth_chunks` → `write_wav`, emitting a
   progress event per chapter (empty-chapter silence guard retained), then
   `assemble.build_m4b`.
4. Output written to `library/<id>/book.m4b` + `cover.jpg` + `manifest.json`.
   Library refreshes; the player streams via the range endpoint.

**Manifest schema** (`library/<id>/manifest.json`): `id, title, author, voice,
speed, created (server-generated ISO timestamp), durationSeconds, sizeBytes,
chapters: [{title, startMs, endMs}], coverFile`.

## Error handling

- Startup checks: ffmpeg/ffprobe and espeak-ng presence → a clear UI banner with
  install guidance if missing (don't hard-crash the server).
- Validate uploads are readable text; reject empty input with a friendly message.
- Per-chunk synth retry/skip is retained; a chapter that yields no audio gets the
  existing 0.5s-silence guard.
- Render-job failure emits an SSE `error` event surfaced in the progress panel; the
  partial `library/<id>/` workspace is cleaned or marked failed (not shown as done).
- Port already in use → server picks the next free port and reports it.

## Testing

- `pipeline/ingest.py` — unit tests: Markdown cleaning (headings, emphasis, links,
  scene breaks), `# H1` → chapter title derivation, multi-file ordering, txt passthrough.
- `server.py` routes — FastAPI `TestClient` with the synth layer mocked (a fake
  Synthesizer returning short silence) so tests run with no GPU: voices list,
  ingest preview, render-job lifecycle to completion, library list/detail/delete,
  range request returns 206.
- Existing pipeline tests remain the real-audio coverage (GPU smoke opt-in).
- Frontend — manual verification checklist (vanilla JS glue): import+reorder,
  audition, generate+live progress, library open, player seek-by-chapter.

## Tech stack additions

`fastapi`, `uvicorn`, `python-multipart` (uploads), `httpx` (TestClient dep).
Added to `requirements.txt`. Frontend: no dependencies / no build.

## Out of scope (YAGNI)

- Cloud sync, accounts, multi-user.
- Voice cloning (XTTS) — still parked from the original spec.
- Waveform visualization, per-character voices, EPUB/PDF/DOCX import.
- Packaging as a desktop app (Tauri/Electron) — considered and deferred.
