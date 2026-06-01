# Text2Audio — Local AI Audiobook Generator

**Date:** 2026-06-01
**Status:** Approved design, ready for implementation planning

## Goal

Turn a user-written book (plain `.txt`) into a natural-sounding, chaptered
`.m4b` audiobook — entirely free and fully local, no cloud services, no
accounts, no per-use cost.

## Target environment

- **OS:** Windows 11
- **GPU:** NVIDIA RTX 3090 (24 GB VRAM) — narration of a full novel completes in
  minutes. Hardware is not a constraint; any local TTS model is viable.
- **Language/runtime:** Python.

## Decisions (from brainstorming)

| Question        | Decision |
|-----------------|----------|
| Voice quality   | Natural & human-like |
| Narrator voice  | High-quality **preset** voices by default (recommend); optional voice **cloning** as a later add-on |
| TTS engine      | **Kokoro-82M** (Apache-licensed, natural, multiple preset narrators, fast on GPU) as default. **XTTS-v2** reserved for optional future voice cloning. |
| Input format    | Plain text `.txt` |
| Output format   | **M4B** audiobook with chapter markers + metadata |
| App form factor | **Local Gradio web app** (runs in browser, nothing published online) |

## Architecture

A local Gradio web UI on top of a staged processing pipeline. Each stage is a
separate, independently testable module with one responsibility.

```
.txt file
   │
   ▼
[1. Parse & chapter-split]  →  list of chapters (title + text)
   ▼
[2. Chunk]                  →  each chapter split into ~sentence-sized pieces
   ▼
[3. Synthesize (Kokoro)]    →  WAV audio per chunk, on GPU
   ▼
[4. Stitch per chapter]     →  one clean WAV per chapter (+ small gaps)
   ▼
[5. Assemble M4B (ffmpeg)]  →  single .m4b w/ chapter markers + metadata
```

The UI calls the pipeline and reports progress; it contains no audio logic
itself.

### Tech stack (all free / local)

- `kokoro` — text-to-speech (default narration)
- `soundfile` / `numpy` — audio I/O and stitching
- `ffmpeg` — M4B encoding (AAC), chapter markers, metadata, cover art
- `gradio` — local web UI

## Components

### `pipeline/parse.py` — text → chapters

Layered chapter detection (fallback chain), so it works out of the box but stays
controllable:

1. **Explicit marker (most reliable):** lines matching a configurable delimiter
   (default `## Chapter Title`) split chapters and supply the chapter title.
2. **Auto-detect headings:** if no explicit markers, detect heading-like lines —
   `Chapter 1`, `CHAPTER ONE`, `Chapter I` (roman), or short all-caps lines
   bounded by blank lines.
3. **Fallback:** if nothing is found, the whole book becomes a single chapter
   (still produces a valid M4B); the UI warns the user.

Output: ordered list of `{title, text}`. The UI shows this list as a
**detected-chapters preview** before any audio is rendered, so the user confirms
the split first.

### `pipeline/chunk.py` — chapters → chunks

Splits each chapter's text into sentence-sized pieces sized for the TTS model's
input limits. Splits on sentence boundaries; never mid-word. Produces an ordered
list of text chunks per chapter.

### `pipeline/synth.py` — chunks → WAV (Kokoro)

Loads Kokoro once (GPU), exposes the available preset voices, synthesizes each
chunk to a WAV array at the model's sample rate. Supports a speaking-speed
parameter. Includes a `preview(voice)` helper that renders one sample sentence
for the UI's "Preview voice" button.

**Resilience:** if a chunk fails, retry once, then skip it with a logged warning
rather than aborting a long job.

### `pipeline/assemble.py` — WAVs → M4B (ffmpeg)

Stitches chunk WAVs into one WAV per chapter (with a short inter-chunk/silence
gap), records each chapter's duration to compute chapter-marker timestamps, then
invokes `ffmpeg` once to: encode to AAC, embed chapter markers, embed
title/author/cover metadata, and write a single `.m4b`.

Intermediate per-chapter WAVs are retained so a failed M4B step does not waste
the whole render.

### `app.py` — Gradio UI

Elements:
- Upload `.txt` (or pick from a folder)
- Voice dropdown (Kokoro presets) + **Preview voice** button
- Optional metadata: book title, author, cover image
- Speaking-speed slider
- **Generate** button with a live progress bar (chapter X of Y)
- Output: download link to the `.m4b` + the detected-chapters list

## Data flow

1. User uploads `.txt`, picks a voice, optionally sets title/author/cover/speed.
2. `parse` produces chapters → UI shows preview list for confirmation.
3. On Generate: `chunk` → `synth` (per chunk, progress reported) → per-chapter
   WAV stitch → `assemble` to `.m4b`.
4. UI presents the finished `.m4b` for download.

## Error handling

- Validate the upload is readable text before processing.
- Detect missing `ffmpeg` up front with a clear install message.
- Per-chunk synth failure: retry once, then skip with a warning (no crash).
- Keep intermediate WAVs so a late-stage failure is recoverable.
- Empty/short input and "no chapters detected" produce a valid single-chapter
  M4B plus a UI warning.

## Testing strategy

Each stage is testable in isolation:
- `parse`: feed sample texts (explicit markers / auto-headings / none) → assert
  chapter splits and titles.
- `chunk`: assert chunk sizes stay within limits and never break mid-word.
- `synth`: smoke test that a short string yields non-empty audio at the expected
  sample rate (can be skipped in CI without a GPU).
- `assemble`: feed dummy/short WAVs → assert a valid `.m4b` with correct chapter
  count and timestamps (inspect via `ffprobe`).

## Project structure

```
Text2Audio/
  app.py            # Gradio UI
  pipeline/
    parse.py        # txt → chapters
    chunk.py        # chapters → chunks
    synth.py        # chunks → WAV (Kokoro)
    assemble.py     # WAVs → M4B (ffmpeg)
  requirements.txt
  README.md         # setup + how to add chapter markers
```

## Out of scope (YAGNI — possible later)

- Voice cloning (XTTS-v2) — architecture leaves room via the `synth` module.
- Input formats beyond `.txt` (PDF/EPUB/DOCX).
- Per-character voices / dialogue detection.
- Packaging as a one-click desktop launcher.
