# Audio Mastering & Non-Destructive Renders Implementation Plan (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Text2Audio output sound mastered (128k AAC + loudness/high-pass), read more naturally (paragraph-aware pacing), and be non-destructive (keep per-chapter WAVs so any book can be re-mastered in seconds).

**Architecture:** Add a mastering filter chain + bitrate control to the ffmpeg assembly step; add a paragraph-aware chunker and variable-gap synthesis; stop deleting chapter WAVs and record them in the manifest; add `remaster`/`purge_wavs` orchestration + endpoints + UI buttons. The existing Kokoro pipeline and `synth.py` interface stay swappable for Phase 3.

**Tech Stack:** Python 3.11, ffmpeg (loudnorm/highpass), the existing kokoro/soundfile pipeline, FastAPI, pytest (GPU-free via mocked synth), vanilla JS frontend.

---

## Environment notes (already done — do NOT redo)

- venv at `.venv`; use `./.venv/Scripts/python.exe`. ffmpeg 8.1 on PATH. Full deps installed.
- Branch: create `audio-mastering` off `studio-ui` (see Task 0). Git identity fallback: `git -c user.name="Text2Audio" -c user.email="mooja77@gmail.com" commit ...`.
- Existing files (do not break their public APIs): `pipeline/assemble.py` (`build_m4b`, `write_wav`, `_build_ffmetadata`, `_duration_ms`), `pipeline/chunk.py` (`chunk_text`), `pipeline/synth.py` (`SAMPLE_RATE`, `concat_with_gaps`, `Synthesizer.synth_chunks/synth_chunk`), `backend/render.py` (`render_audiobook`, `_render_into`), `backend/library.py` (`Library`), `server.py`, `web/js/library.js`.
- Full suite is green before starting (`./.venv/Scripts/python.exe -m pytest -q` → 48 passed, 1 skipped).

## Locked interfaces (use these names across tasks)

- `pipeline/assemble.py`: `DEFAULT_BITRATE = "128k"`; `MASTER_FILTERS = "highpass=f=80,loudnorm=I=-19:TP=-2:LRA=11"`; `build_m4b(chapter_wavs, output_path, book_title=None, author=None, cover=None, ffmpeg="ffmpeg", master: bool = True, bitrate: str = DEFAULT_BITRATE)`.
- `pipeline/chunk.py`: `chunk_paragraphs(text: str, max_chars: int = 400) -> list[list[str]]`.
- `pipeline/synth.py`: `SENTENCE_GAP = 0.15`; `PARAGRAPH_GAP = 0.6`; `Synthesizer.synth_paragraphs(paragraphs, progress=None) -> np.ndarray`.
- `backend/render.py`: keeps WAVs under `library/<id>/wav/`; manifest gains `wavKept: bool`, `wavFiles: list[str]`, `bitrate: str`, `mastered: bool`. `remaster(library, id, *, bitrate=DEFAULT_BITRATE, master=True) -> dict`; `purge_wavs(library, id) -> dict`.
- `server.py`: `POST /api/library/{id}/remaster` (optional body `{bitrate, master}`), `POST /api/library/{id}/purge-wav`.

---

## Task 0: Branch

- [ ] **Step 1: Create the feature branch off studio-ui**

Run:
```bash
git checkout studio-ui
git checkout -b audio-mastering
git branch --show-current
```
Expected: prints `audio-mastering`.

(No commit — this just establishes the branch. All Phase 1 work lands here.)

---

## Task 1: Mastering filters + bitrate in `build_m4b`

**Files:** Modify `pipeline/assemble.py`; modify `tests/test_assemble.py`

- [ ] **Step 1: Add the failing tests** — append to `tests/test_assemble.py`:

```python
def test_build_m4b_applies_master_filters_and_bitrate(tmp_path, monkeypatch):
    import pipeline.assemble as asm
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        class R: pass
        return R()

    # write a real wav so duration probing works, but stub ffmpeg invocation
    import numpy as np
    from pipeline.synth import SAMPLE_RATE
    wav = str(tmp_path / "c.wav")
    asm.write_wav(np.zeros(SAMPLE_RATE, dtype=np.float32), wav)
    monkeypatch.setattr(asm.subprocess, "run", fake_run)
    monkeypatch.setattr(asm.shutil, "which", lambda x: "ffmpeg")

    asm.build_m4b([("C1", wav)], str(tmp_path / "out.m4b"), master=True)
    cmd = captured["cmd"]
    assert "-af" in cmd
    af = cmd[cmd.index("-af") + 1]
    assert "loudnorm" in af and "highpass" in af
    assert "128k" in cmd  # default bitrate


def test_build_m4b_master_false_omits_filters(tmp_path, monkeypatch):
    import pipeline.assemble as asm
    captured = {}
    monkeypatch.setattr(asm.subprocess, "run", lambda cmd, **k: captured.setdefault("cmd", cmd))
    monkeypatch.setattr(asm.shutil, "which", lambda x: "ffmpeg")
    import numpy as np
    from pipeline.synth import SAMPLE_RATE
    wav = str(tmp_path / "c.wav")
    asm.write_wav(np.zeros(SAMPLE_RATE, dtype=np.float32), wav)
    asm.build_m4b([("C1", wav)], str(tmp_path / "out.m4b"), master=False, bitrate="96k")
    cmd = captured["cmd"]
    assert "-af" not in cmd
    assert "96k" in cmd
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_assemble.py -k master -v` → FAIL.

- [ ] **Step 3: Edit `pipeline/assemble.py`.**

(a) Add constants after the existing `MANIFEST`-style constants near the top (after the imports and the `from pipeline.synth import SAMPLE_RATE` line):

```python
DEFAULT_BITRATE = "128k"
MASTER_FILTERS = "highpass=f=80,loudnorm=I=-19:TP=-2:LRA=11"
```

(b) Change the `build_m4b` signature and the ffmpeg command tail. Replace the existing signature line:

```python
def build_m4b(chapter_wavs, output_path: str, book_title=None, author=None,
              cover=None, ffmpeg: str = "ffmpeg") -> str:
```

with:

```python
def build_m4b(chapter_wavs, output_path: str, book_title=None, author=None,
              cover=None, ffmpeg: str = "ffmpeg", master: bool = True,
              bitrate: str = DEFAULT_BITRATE) -> str:
```

(c) Replace the final command-assembly tail. Find:

```python
    cmd += ["-map", "0:a", "-map_metadata", "1"]
    if cover:
        cmd += ["-map", "2:v", "-disposition:v", "attached_pic", "-c:v", "mjpeg"]
    cmd += ["-c:a", "aac", "-b:a", "64k", output_path]
```

and replace with:

```python
    cmd += ["-map", "0:a", "-map_metadata", "1"]
    if cover:
        cmd += ["-map", "2:v", "-disposition:v", "attached_pic", "-c:v", "mjpeg"]
    if master:
        cmd += ["-af", MASTER_FILTERS]
    cmd += ["-c:a", "aac", "-b:a", bitrate, output_path]
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_assemble.py -v` → all pass (existing real-ffmpeg test + the 2 new monkeypatched ones).

- [ ] **Step 5: Commit** — `git add pipeline/assemble.py tests/test_assemble.py && git commit -m "feat: master filters + configurable bitrate in build_m4b"`

---

## Task 2: Paragraph-aware chunking

**Files:** Modify `pipeline/chunk.py`; modify `tests/test_chunk.py`

- [ ] **Step 1: Add the failing tests** — append to `tests/test_chunk.py`:

```python
from pipeline.chunk import chunk_paragraphs


def test_chunk_paragraphs_groups_by_blank_line():
    text = "First para sentence one. Sentence two.\n\nSecond para only."
    paras = chunk_paragraphs(text)
    assert len(paras) == 2
    assert all(isinstance(p, list) for p in paras)
    assert "Second para only." in paras[1][0]


def test_chunk_paragraphs_respects_max_chars():
    text = "One sentence here. Two sentence here. Three sentence here."
    paras = chunk_paragraphs(text, max_chars=25)
    flat = [c for p in paras for c in p]
    assert all(len(c) <= 25 for c in flat)
    assert len(paras) == 1  # single paragraph, multiple chunks
    assert len(paras[0]) == 3


def test_chunk_paragraphs_drops_empty():
    text = "\n\n  \n\nReal text.\n\n\n"
    paras = chunk_paragraphs(text)
    assert len(paras) == 1 and paras[0] == ["Real text."]


def test_chunk_paragraphs_empty_input():
    assert chunk_paragraphs("   \n\n  ") == []
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_chunk.py -k paragraphs -v` → FAIL (ImportError).

- [ ] **Step 3: Edit `pipeline/chunk.py`** — append this function (the existing `chunk_text` and `_hard_split` stay unchanged):

```python
def chunk_paragraphs(text: str, max_chars: int = 400) -> list[list[str]]:
    """Split text into paragraphs (on blank lines), each a list of sentence chunks."""
    paragraphs = re.split(r"\n\s*\n", text)
    out = []
    for para in paragraphs:
        chunks = chunk_text(para, max_chars=max_chars)
        if chunks:
            out.append(chunks)
    return out
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_chunk.py -v` → all pass.

- [ ] **Step 5: Commit** — `git add pipeline/chunk.py tests/test_chunk.py && git commit -m "feat: paragraph-aware chunking"`

---

## Task 3: Variable-gap synthesis

**Files:** Modify `pipeline/synth.py`; modify `tests/test_synth.py`

- [ ] **Step 1: Add the failing tests** — append to `tests/test_synth.py`:

```python
from pipeline.synth import SENTENCE_GAP, PARAGRAPH_GAP


def test_gap_constants():
    assert SENTENCE_GAP == 0.15 and PARAGRAPH_GAP == 0.6


def test_synth_paragraphs_uses_variable_gaps(monkeypatch):
    from pipeline.synth import Synthesizer

    # Build a Synthesizer without importing kokoro: bypass __init__.
    synth = Synthesizer.__new__(Synthesizer)
    synth.voice, synth.speed = "x", 1.0
    # one fixed 1000-sample clip per chunk
    monkeypatch.setattr(synth, "synth_chunk", lambda text: np.ones(1000, dtype=np.float32))

    # two paragraphs, one chunk each -> clipA + PARAGRAPH_GAP + clipB
    out = synth.synth_paragraphs([["a"], ["b"]])
    expected = 1000 + int(PARAGRAPH_GAP * SAMPLE_RATE) + 1000
    assert out.shape[0] == expected

    # one paragraph, two chunks -> clip + SENTENCE_GAP + clip
    out2 = synth.synth_paragraphs([["a", "b"]])
    expected2 = 1000 + int(SENTENCE_GAP * SAMPLE_RATE) + 1000
    assert out2.shape[0] == expected2
```

(`np` and `SAMPLE_RATE` are already imported at the top of `tests/test_synth.py`.)

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_synth.py -k "gap or paragraphs" -v` → FAIL.

- [ ] **Step 3: Edit `pipeline/synth.py`.**

(a) Add constants after `SAMPLE_RATE = 24000`:

```python
SENTENCE_GAP = 0.15
PARAGRAPH_GAP = 0.6
```

(b) Add this method to the `Synthesizer` class (after `synth_chunks`):

```python
    def synth_paragraphs(self, paragraphs, progress=None) -> np.ndarray:
        total = sum(len(p) for p in paragraphs)
        done = 0
        para_audios = []
        for para in paragraphs:
            chunk_audios = []
            for chunk in para:
                audio = None
                for _attempt in range(2):  # one retry
                    try:
                        audio = self.synth_chunk(chunk)
                        break
                    except Exception:
                        audio = None
                if audio is not None and len(audio) > 0:
                    chunk_audios.append(audio)
                done += 1
                if progress is not None:
                    progress(done, total)
            joined = concat_with_gaps(chunk_audios, gap_seconds=SENTENCE_GAP)
            if len(joined) > 0:
                para_audios.append(joined)
        return concat_with_gaps(para_audios, gap_seconds=PARAGRAPH_GAP)
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_synth.py -v` → all pass (5 unit + 2 new + 1 skipped GPU smoke).

- [ ] **Step 5: Commit** — `git add pipeline/synth.py tests/test_synth.py && git commit -m "feat: paragraph-aware variable-gap synthesis"`

---

## Task 4: Non-destructive render + remaster + purge

**Files:** Modify `backend/render.py`; modify `tests/test_render.py`

- [ ] **Step 1: Add the failing tests** — append to `tests/test_render.py` (the file already imports `numpy as np`, `Library`, `render_audiobook`, `SAMPLE_RATE`, and defines `FakeSynth`):

```python
import os
from backend.render import remaster, purge_wavs


class FakeSynthP(FakeSynth):
    # FakeSynth only defines synth_chunks; render now uses synth_paragraphs.
    def synth_paragraphs(self, paragraphs, progress=None):
        n = sum(len(p) for p in paragraphs)
        return np.zeros(int(0.2 * SAMPLE_RATE) * max(1, n), dtype=np.float32)


def test_render_keeps_wavs_and_marks_manifest(tmp_path):
    lib = Library(str(tmp_path))
    book = "## Chapter 1 - One\nChapter 1. One.\n\nHello there.\n\nSecond para."
    m = render_audiobook(book_text=book, voice="bm_george", speed=0.9, title="T",
                         author="", cover_path=None, library=lib, job_id="j1",
                         emit=lambda e: None, synth_factory=FakeSynthP)
    assert m["wavKept"] is True
    assert m["mastered"] is True and m["bitrate"] == "128k"
    assert len(m["wavFiles"]) == 1
    assert os.path.isfile(os.path.join(str(tmp_path), "j1", m["wavFiles"][0]))


def test_remaster_rebuilds_from_kept_wavs(tmp_path):
    lib = Library(str(tmp_path))
    book = "## Chapter 1 - One\nHi.\n\n## Chapter 2 - Two\nBye."
    render_audiobook(book_text=book, voice="af_heart", speed=1.0, title="T", author="",
                     cover_path=None, library=lib, job_id="j2", emit=lambda e: None,
                     synth_factory=FakeSynthP)
    before = os.path.getmtime(lib.audio_path("j2"))
    m = remaster(lib, "j2", bitrate="96k")
    assert m["bitrate"] == "96k"
    import json
    saved = lib.get("j2")
    assert saved["bitrate"] == "96k"
    # m4b rebuilt and still has 2 chapters
    import subprocess
    probe = subprocess.run(["ffprobe", "-print_format", "json", "-show_chapters",
                            lib.audio_path("j2")], capture_output=True, text=True, check=True)
    assert len(json.loads(probe.stdout)["chapters"]) == 2


def test_purge_then_remaster_raises(tmp_path):
    lib = Library(str(tmp_path))
    render_audiobook(book_text="## A\n\nhi", voice="af_heart", speed=1.0, title="T",
                     author="", cover_path=None, library=lib, job_id="j3",
                     emit=lambda e: None, synth_factory=FakeSynthP)
    m = purge_wavs(lib, "j3")
    assert m["wavKept"] is False and m["wavFiles"] == []
    assert not os.path.isdir(os.path.join(str(tmp_path), "j3", "wav"))
    import pytest
    with pytest.raises(Exception):
        remaster(lib, "j3")
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_render.py -k "wav or remaster or purge" -v` → FAIL.

- [ ] **Step 3: Rewrite `backend/render.py`.** Replace the entire file with:

```python
"""Orchestrate the TTS pipeline into a finished audiobook + manifest."""
import datetime
import os
import shutil

import numpy as np
import soundfile as sf

from pipeline.parse import parse_chapters
from pipeline.chunk import chunk_paragraphs
from pipeline.synth import Synthesizer, PRESET_VOICES, SAMPLE_RATE
from pipeline.assemble import write_wav, build_m4b, DEFAULT_BITRATE

WAV_SUBDIR = "wav"


def _wav_dir(library, job_id: str) -> str:
    d = os.path.join(library.new_dir(job_id), WAV_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


def _chapter_meta(chapter_wavs):
    meta, start = [], 0
    for title, wp in chapter_wavs:
        info = sf.info(wp)
        dur = int(round(info.frames / info.samplerate * 1000))
        meta.append({"title": title, "startMs": start, "endMs": start + dur})
        start += dur
    return meta


def render_audiobook(*, book_text, voice, speed, title, author, cover_path,
                     library, job_id, emit, synth_factory=Synthesizer) -> dict:
    chapters = parse_chapters(book_text, default_title=title or "Audiobook")
    workdir = library.new_dir(job_id)
    try:
        return _render_into(workdir, chapters, voice=voice, speed=speed, title=title,
                            author=author, cover_path=cover_path, library=library,
                            job_id=job_id, emit=emit, synth_factory=synth_factory)
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


def _render_into(workdir, chapters, *, voice, speed, title, author, cover_path,
                 library, job_id, emit, synth_factory) -> dict:
    synth = synth_factory(voice=voice, lang_code=PRESET_VOICES[voice], speed=float(speed))
    wav_dir = _wav_dir(library, job_id)

    n = len(chapters)
    chapter_wavs = []
    wav_files = []
    for i, ch in enumerate(chapters):
        emit({"type": "progress", "chapterIndex": i, "chapterCount": n,
              "chapterTitle": ch.title, "percent": round(i / max(1, n) * 100)})
        audio = synth.synth_paragraphs(chunk_paragraphs(ch.text))
        if len(audio) == 0:
            audio = np.zeros(int(0.5 * SAMPLE_RATE), dtype=np.float32)
        rel = os.path.join(WAV_SUBDIR, f"chapter_{i + 1:03d}.wav")
        write_wav(audio, os.path.join(workdir, rel))
        chapter_wavs.append((ch.title, os.path.join(workdir, rel)))
        wav_files.append(rel)

    cover_dest = None
    if cover_path:
        cover_dest = os.path.join(workdir, "cover.jpg")
        shutil.copyfile(cover_path, cover_dest)

    out = library.audio_path(job_id)
    build_m4b(chapter_wavs, out, book_title=title or None, author=author or None,
              cover=cover_dest, master=True, bitrate=DEFAULT_BITRATE)

    chapters_meta = _chapter_meta(chapter_wavs)
    total_ms = chapters_meta[-1]["endMs"] if chapters_meta else 0

    manifest = {
        "id": job_id, "title": title or "Audiobook", "author": author or "",
        "voice": voice, "speed": float(speed),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "durationSeconds": round(total_ms / 1000, 1), "sizeBytes": os.path.getsize(out),
        "chapters": chapters_meta, "coverFile": "cover.jpg" if cover_dest else None,
        "wavKept": True, "wavFiles": wav_files, "bitrate": DEFAULT_BITRATE, "mastered": True,
    }
    library.save_manifest(job_id, manifest)
    emit({"type": "done", "libraryId": job_id, "percent": 100})
    return manifest


def remaster(library, id, *, bitrate=DEFAULT_BITRATE, master=True) -> dict:
    m = library.get(id)
    if m is None:
        raise FileNotFoundError(f"no such audiobook: {id}")
    if not m.get("wavKept") or not m.get("wavFiles"):
        raise ValueError("source audio was purged; re-render required to re-master")
    workdir = library.new_dir(id)
    chapter_wavs = [(c["title"], os.path.join(workdir, rel))
                    for c, rel in zip(m["chapters"], m["wavFiles"])]
    out = library.audio_path(id)
    build_m4b(chapter_wavs, out, book_title=m["title"] or None, author=m["author"] or None,
              cover=os.path.join(workdir, m["coverFile"]) if m.get("coverFile") else None,
              master=master, bitrate=bitrate)
    m["bitrate"] = bitrate
    m["mastered"] = master
    m["sizeBytes"] = os.path.getsize(out)
    library.save_manifest(id, m)
    return m


def purge_wavs(library, id) -> dict:
    m = library.get(id)
    if m is None:
        raise FileNotFoundError(f"no such audiobook: {id}")
    shutil.rmtree(os.path.join(library.new_dir(id), WAV_SUBDIR), ignore_errors=True)
    m["wavKept"] = False
    m["wavFiles"] = []
    library.save_manifest(id, m)
    return m
```

NOTE: `_render_into` now uses `synth.synth_paragraphs` + `chunk_paragraphs`. The existing `tests/test_render.py` `FakeSynth` only defines `synth_chunks`, so the new tests add `FakeSynthP` with `synth_paragraphs`. The pre-existing render tests (`test_render_creates_m4b_and_manifest`, `test_render_empty_chapter_gets_silence`) call `render_audiobook` with `FakeSynth` (no `synth_paragraphs`) and will now FAIL — update them in Step 4.

- [ ] **Step 4: Fix the two pre-existing render tests** to use a fake that implements `synth_paragraphs`. In `tests/test_render.py`, change the original `FakeSynth` class so it ALSO supports paragraphs (add the method to the existing class rather than only `FakeSynthP`):

Replace the existing `FakeSynth` class definition:

```python
class FakeSynth:
    def __init__(self, voice, lang_code, speed=1.0):
        self.voice = voice
    def synth_chunks(self, chunks, progress=None):
        # ~0.2s of silence per non-empty chunk list
        return np.zeros(int(0.2 * SAMPLE_RATE) * max(1, len(chunks)), dtype=np.float32)
```

with:

```python
class FakeSynth:
    def __init__(self, voice, lang_code, speed=1.0):
        self.voice = voice
    def synth_chunks(self, chunks, progress=None):
        return np.zeros(int(0.2 * SAMPLE_RATE) * max(1, len(chunks)), dtype=np.float32)
    def synth_paragraphs(self, paragraphs, progress=None):
        n = sum(len(p) for p in paragraphs)
        return np.zeros(int(0.2 * SAMPLE_RATE) * max(1, n), dtype=np.float32)
```

Then `FakeSynthP` (added in Step 1) can simply subclass it without redefining the method — change its body to `pass`:

```python
class FakeSynthP(FakeSynth):
    pass
```

- [ ] **Step 5: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_render.py -v` → all pass (2 updated original + 3 new).

- [ ] **Step 6: Commit** — `git add backend/render.py tests/test_render.py && git commit -m "feat: non-destructive renders + remaster/purge"`

---

## Task 5: Remaster + purge endpoints

**Files:** Modify `server.py`; modify `tests/test_api.py`

- [ ] **Step 1: Add the failing tests** — append to `tests/test_api.py` (it already defines the `client` fixture, `_FakeSynth`, `_make_one`, and imports `numpy as np`/`SAMPLE_RATE`). First, the API render path uses `synth_paragraphs` now, so `_FakeSynth` needs it — add the method by appending a subclass-free patch. Add these tests:

```python
def test_remaster_endpoint_updates_manifest(client, monkeypatch):
    import server
    jid = _make_one(client, server, monkeypatch, "RemasterMe")
    r = client.post(f"/api/library/{jid}/remaster", json={"bitrate": "96k"})
    assert r.status_code == 200
    assert r.json()["bitrate"] == "96k"
    assert client.get(f"/api/library/{jid}").json()["bitrate"] == "96k"


def test_purge_endpoint_flips_flags_and_blocks_remaster(client, monkeypatch):
    import server
    jid = _make_one(client, server, monkeypatch)
    p = client.post(f"/api/library/{jid}/purge-wav")
    assert p.status_code == 200 and p.json()["wavKept"] is False
    # remaster after purge -> 400
    assert client.post(f"/api/library/{jid}/remaster").status_code == 400


def test_remaster_bad_id_404(client):
    assert client.post("/api/library/not-hex-id/remaster").status_code == 404
```

Also, update `_FakeSynth` in `tests/test_api.py` so the render path works with `synth_paragraphs`. Find the existing `_FakeSynth` class:

```python
class _FakeSynth:
    def __init__(self, voice, lang_code, speed=1.0):
        pass
    def synth_chunks(self, chunks, progress=None):
        return np.zeros(int(0.1 * SAMPLE_RATE), dtype=np.float32)
```

and add a `synth_paragraphs` method to it:

```python
class _FakeSynth:
    def __init__(self, voice, lang_code, speed=1.0):
        pass
    def synth_chunks(self, chunks, progress=None):
        return np.zeros(int(0.1 * SAMPLE_RATE), dtype=np.float32)
    def synth_paragraphs(self, paragraphs, progress=None):
        return np.zeros(int(0.1 * SAMPLE_RATE), dtype=np.float32)
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -k "remaster or purge" -v` → FAIL (404 on the endpoints).

- [ ] **Step 3: Edit `server.py`.**

(a) Extend the render import. Change:

```python
from backend.render import render_audiobook
```

to:

```python
from backend.render import render_audiobook, remaster, purge_wavs
```

(b) Add a request model near the other models (e.g. after `RetagRequest`):

```python
class RemasterRequest(BaseModel):
    bitrate: str = "128k"
    master: bool = True
```

(c) Add these routes immediately BEFORE the `# IMPORTANT: keep this static mount` comment:

```python
@app.post("/api/library/{id}/remaster")
def library_remaster(id: str, req: RemasterRequest):
    _check_id(id)
    try:
        return remaster(library, id, bitrate=req.bitrate, master=req.master)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/library/{id}/purge-wav")
def library_purge(id: str):
    _check_id(id)
    try:
        return purge_wavs(library, id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v` → all pass.

- [ ] **Step 5: Run the FULL suite** — `./.venv/Scripts/python.exe -m pytest -q` → all pass (1 skipped GPU smoke). Fix any red before committing.

- [ ] **Step 6: Commit** — `git add server.py tests/test_api.py && git commit -m "feat: remaster + purge-wav endpoints"`

---

## Task 6: Library UI — Re-master + Purge buttons

**Files:** Modify `web/js/library.js`. Verified manually + via the controller's browser pass.

- [ ] **Step 1: Edit the `detail` method in `web/js/library.js`.** Replace the actions row markup and bindings. Find the block that builds the detail view actions (the `<div style="margin-top:16px;display:flex;gap:8px">` containing Retag/Delete and their `onclick` handlers) and replace the actions `<div>` plus its handlers with:

```javascript
    el.innerHTML = `<button class="backlink" id="back">← Library</button>
      <div id="playerwrap"></div>
      <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn" id="retag">Retag</button>
        ${item.wavKept ? '<button class="btn" id="remaster">Re-master</button>' +
          '<button class="btn" id="purge">Purge source audio</button>' : ''}
        <button class="btn" id="del">Delete</button></div>
      ${item.wavKept ? '<div class="muted" style="margin-top:8px;font-size:12px">Source audio kept — you can re-master instantly. Purge to reclaim disk space.</div>' : ''}`;
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
    if (item.wavKept) {
      document.getElementById("remaster").onclick = async () => {
        T2A.toast("Re-mastering…");
        await T2A.api(`/api/library/${id}/remaster`, { method: "POST",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
        T2A.toast("Re-mastered"); this.detail(id); };
      document.getElementById("purge").onclick = async () => {
        if (!confirm("Delete the source WAVs? You won't be able to re-master without re-rendering.")) return;
        await T2A.api(`/api/library/${id}/purge-wav`, { method: "POST" });
        T2A.toast("Source audio purged"); this.detail(id); };
    }
```

(Leave the rest of `library.js` — the `render` grid method and `Player` usage — unchanged.)

- [ ] **Step 2: Verify the app builds the UI** — start the server without a browser and confirm `library.js` is served and `app` imports cleanly:

Run (PowerShell): `$env:T2A_NO_BROWSER=1; Start-Process -NoNewWindow ./.venv/Scripts/python.exe server.py; Start-Sleep 3; (Invoke-WebRequest http://127.0.0.1:8765/js/library.js).StatusCode; Get-Process python | Stop-Process`
Expected: `200`.

- [ ] **Step 3: Commit** — `git add web/js/library.js && git commit -m "feat: Re-master + Purge buttons in library detail"`

---

## Task 7: End-to-end verification

**Files:** none (verification only). Controller runs this; not a subagent unit test.

- [ ] **Step 1: Full suite** — `./.venv/Scripts/python.exe -m pytest -q` → all pass (1 skipped GPU smoke).

- [ ] **Step 2: Live mastering check (GPU).** Render a short book through the running server (real Kokoro) and confirm the output is mastered and re-masterable:

Run the server (PowerShell, background): `$env:T2A_NO_BROWSER=1; $env:PHONEMIZER_ESPEAK_LIBRARY="C:\Program Files\eSpeak NG\libespeak-ng.dll"; $env:PHONEMIZER_ESPEAK_PATH="C:\Program Files\eSpeak NG\espeak-ng.exe"; ./.venv/Scripts/python.exe server.py`

Then (controller, via the Playwright MCP against `http://127.0.0.1:8765`, or via the API directly): render `samples/sample_book.txt`, wait for done, then:
- `ffprobe -show_format library/<id>/book.m4b` → confirm AAC bitrate ≈ 128k.
- Confirm `library/<id>/wav/` contains the chapter WAV(s) and the manifest has `wavKept: true`, `mastered: true`, `bitrate: "128k"`.
- Measure loudness: `ffmpeg -i library/<id>/book.m4b -af loudnorm=print_format=json -f null -` → integrated loudness near −19 LUFS.
- Hit `POST /api/library/<id>/remaster` with `{"bitrate":"96k"}` → manifest bitrate becomes `96k`, m4b rebuilt, chapters intact.
Stop the server when done.

- [ ] **Step 3: No commit** (verification only). If anything fails, fix in the relevant task's files and re-run.

---

## Self-review notes (addressed)

- **Spec coverage:** bitrate→128k + master filters (T1), paragraph chunking (T2), variable gaps (T3), non-destructive WAVs + remaster + purge + manifest fields (T4), endpoints (T5), UI buttons (T6), e2e incl. loudness measurement (T7). All spec sections map to a task.
- **Type/interface consistency:** `build_m4b(..., master, bitrate)`, `DEFAULT_BITRATE`/`MASTER_FILTERS`, `chunk_paragraphs`, `SENTENCE_GAP`/`PARAGRAPH_GAP`/`synth_paragraphs`, manifest keys `wavKept/wavFiles/bitrate/mastered`, and `remaster(...)/purge_wavs(...)` are used identically across tasks and the UI reads exactly those manifest keys.
- **Breaking-change handled:** `render` switching to `synth_paragraphs` breaks the old `FakeSynth` (synth_chunks-only); T4 Step 4 and T5 Step 1 update the fakes in `test_render.py` and `test_api.py` so the whole suite stays green.
- **No placeholders:** every code/test step is complete and runnable.
- **Out of scope:** pronunciation (Phase 2), cloning engine (Phase 3), configurable LUFS in UI.
```
