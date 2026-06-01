# Text2Audio Audiobook Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Gradio web app that turns a plain-text book into a natural-sounding, chaptered `.m4b` audiobook using the Kokoro-82M TTS model on the GPU.

**Architecture:** A 5-stage pipeline (parse → chunk → synthesize → stitch → assemble) wrapped in a local Gradio UI. Each stage is a focused, independently testable module. Audio is generated per chunk by Kokoro, concatenated per chapter to WAV, then combined into a single `.m4b` with chapter markers by ffmpeg.

**Tech Stack:** Python 3.10–3.12, `kokoro` (TTS), `torch` (CUDA), `soundfile` + `numpy` (audio), `ffmpeg`/`ffprobe` (M4B assembly), `gradio` (UI), `pytest` (tests).

---

## Verified Kokoro facts (use these — do not re-derive)

- Install: `pip install kokoro soundfile`. Needs **espeak-ng** system dep (Windows: install the `.msi` from the espeak-ng GitHub releases; if not auto-found, set env vars `PHONEMIZER_ESPEAK_LIBRARY` → `C:\Program Files\eSpeak NG\libespeak-ng.dll` and `PHONEMIZER_ESPEAK_PATH` → `C:\Program Files\eSpeak NG\espeak-ng.exe`).
- Needs a **CUDA-enabled torch build** (install from pytorch.org CUDA index, not the CPU wheel).
- API:
  ```python
  from kokoro import KPipeline
  pipeline = KPipeline(lang_code='a', device='cuda')   # 'a'=American, 'b'=British
  for graphemes, phonemes, audio in pipeline(text, voice='af_heart', speed=1):
      ...  # audio = 1-D float32 numpy array, 24000 Hz mono
  ```
- `pipeline(...)` returns a **generator**; each item unpacks as `(graphemes, phonemes, audio)`.
- Sample rate: **24000 Hz**, mono.
- `lang_code` MUST match the voice prefix (`a`↔`af_*`/`am_*`, `b`↔`bf_*`/`bm_*`).
- Voices (subset we expose): American F `af_heart, af_bella, af_nicole, af_sarah, af_sky`; American M `am_michael, am_adam, am_echo, am_liam`; British F `bf_emma, bf_isabella, bf_alice`; British M `bm_george, bm_lewis, bm_daniel`.
- License: Apache-2.0.

## File structure

```
Text2Audio/
  app.py                    # Gradio UI (wiring only)
  pipeline/
    __init__.py
    parse.py                # txt -> [Chapter(title, text)]
    chunk.py                # chapter text -> [str chunks]
    synth.py                # chunks -> numpy audio (Kokoro) + audio helpers + voice list
    assemble.py             # chapter WAVs -> .m4b (ffmpeg)
  tests/
    __init__.py
    test_parse.py
    test_chunk.py
    test_synth.py
    test_assemble.py
  samples/
    sample_book.txt         # tiny demo book for end-to-end test
  requirements.txt
  README.md
```

Interfaces locked across tasks (use these exact names/signatures):
- `pipeline/parse.py`: `@dataclass Chapter(title: str, text: str)`; `parse_chapters(text: str, marker: str = "## ", default_title: str = "Audiobook") -> list[Chapter]`
- `pipeline/chunk.py`: `chunk_text(text: str, max_chars: int = 400) -> list[str]`
- `pipeline/synth.py`: `SAMPLE_RATE = 24000`; `PRESET_VOICES: dict[str, str]` (voice_id → lang_code); `concat_with_gaps(audio_arrays, gap_seconds=0.3, sample_rate=SAMPLE_RATE) -> np.ndarray`; `class Synthesizer(voice='af_heart', lang_code='a', device='cuda', speed=1.0)` with `.synth_chunk(text) -> np.ndarray`, `.synth_chunks(chunks, progress=None) -> np.ndarray`, `.preview(text=...) -> np.ndarray`
- `pipeline/assemble.py`: `write_wav(audio, path, sample_rate=SAMPLE_RATE) -> str`; `build_m4b(chapter_wavs: list[tuple[str, str]], output_path: str, book_title=None, author=None, cover=None, ffmpeg="ffmpeg") -> str`

---

## Task 1: Project scaffold and dependencies

**Files:**
- Create: `requirements.txt`, `pipeline/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
kokoro>=0.9.4
soundfile>=0.12
numpy>=1.24
gradio>=4.0
pytest>=8.0
```

- [ ] **Step 2: Create empty package files**

Create `pipeline/__init__.py` with a single line:

```python
"""Text2Audio processing pipeline."""
```

Create `tests/__init__.py` as an empty file (0 bytes).

- [ ] **Step 3: Create and activate a virtual environment, install deps**

Run (PowerShell, from project root):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --index-url https://download.pytorch.org/whl/cu124 torch
pip install -r requirements.txt
```

Expected: torch installs a CUDA build; other deps install without error. (espeak-ng + ffmpeg are system installs covered in the README; not needed until Tasks 4–5.)

- [ ] **Step 4: Verify pytest runs (no tests yet)**

Run: `pytest -q`
Expected: "no tests ran" (exit code 5) — confirms pytest is installed and discovers the `tests/` package.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt pipeline/__init__.py tests/__init__.py
git commit -m "chore: project scaffold and dependencies"
```

---

## Task 2: Chapter parsing (`pipeline/parse.py`)

**Files:**
- Create: `pipeline/parse.py`
- Test: `tests/test_parse.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_parse.py`:

```python
from pipeline.parse import parse_chapters, Chapter


def test_explicit_markers_split_and_title():
    text = "## Intro\nHello world.\n## Chapter Two\nMore text here."
    chapters = parse_chapters(text)
    assert chapters == [
        Chapter("Intro", "Hello world."),
        Chapter("Chapter Two", "More text here."),
    ]


def test_autodetect_chapter_headings():
    text = "Chapter 1\nThe beginning.\n\nChapter 2\nThe middle."
    chapters = parse_chapters(text)
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
    assert chapters[0].text == "The beginning."
    assert chapters[1].text == "The middle."


def test_autodetect_allcaps_heading():
    text = "PROLOGUE\n\nIt was a dark night.\n\nTHE END\n\nThat is all."
    chapters = parse_chapters(text)
    assert [c.title for c in chapters] == ["PROLOGUE", "THE END"]


def test_text_before_first_heading_becomes_introduction():
    text = "Front matter line.\nChapter 1\nReal content."
    chapters = parse_chapters(text)
    assert chapters[0] == Chapter("Introduction", "Front matter line.")
    assert chapters[1] == Chapter("Chapter 1", "Real content.")


def test_no_headings_single_chapter_uses_default_title():
    text = "Just a blob of text.\nWith two lines."
    chapters = parse_chapters(text, default_title="My Book")
    assert len(chapters) == 1
    assert chapters[0].title == "My Book"
    assert "blob of text" in chapters[0].text


def test_empty_input_returns_empty_list():
    assert parse_chapters("   \n  \n") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_parse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.parse'`.

- [ ] **Step 3: Implement `pipeline/parse.py`**

```python
"""Parse plain-text books into chapters."""
import re
from dataclasses import dataclass

_CHAPTER_RE = re.compile(r"^\s*chapter\b.*", re.IGNORECASE)


@dataclass
class Chapter:
    title: str
    text: str


def _is_explicit_heading(line: str, token: str) -> bool:
    return line.strip().startswith(token)


def _explicit_title(line: str, token: str) -> str:
    return line.strip()[len(token):].strip()


def _is_auto_heading(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _CHAPTER_RE.match(s):
        return True
    # Short all-caps line containing at least one letter, used as a heading.
    return s.isupper() and any(ch.isalpha() for ch in s) and len(s) <= 50


def parse_chapters(text: str, marker: str = "## ", default_title: str = "Audiobook") -> list[Chapter]:
    lines = text.splitlines()
    token = marker.strip()

    use_explicit = any(_is_explicit_heading(ln, token) for ln in lines)
    if use_explicit:
        def is_heading(ln): return _is_explicit_heading(ln, token)
        def get_title(ln): return _explicit_title(ln, token)
    else:
        def is_heading(ln): return _is_auto_heading(ln)
        def get_title(ln): return ln.strip()

    chapters: list[Chapter] = []
    current_title = None
    buf: list[str] = []

    def flush(title):
        body = "\n".join(buf).strip()
        if title is None:
            if body:
                chapters.append(Chapter("Introduction", body))
        else:
            chapters.append(Chapter(title, body))

    for ln in lines:
        if is_heading(ln):
            if current_title is not None or "".join(buf).strip():
                flush(current_title)
            current_title = get_title(ln)
            buf = []
        else:
            buf.append(ln)

    if current_title is not None or "".join(buf).strip():
        flush(current_title)

    if not chapters:
        return []
    if len(chapters) == 1 and chapters[0].title == "Introduction":
        chapters[0] = Chapter(default_title, chapters[0].text)
    return chapters
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_parse.py -v`
Expected: PASS (all 6 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/parse.py tests/test_parse.py
git commit -m "feat: chapter parsing with marker, heading, and fallback detection"
```

---

## Task 3: Sentence chunking (`pipeline/chunk.py`)

**Files:**
- Create: `pipeline/chunk.py`
- Test: `tests/test_chunk.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_chunk.py`:

```python
from pipeline.chunk import chunk_text


def test_empty_returns_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_single_chunk():
    assert chunk_text("Hello there. How are you?") == ["Hello there. How are you?"]


def test_groups_sentences_under_limit():
    text = "One sentence here. Two sentence here. Three sentence here."
    chunks = chunk_text(text, max_chars=25)
    assert len(chunks) == 3
    assert all(len(c) <= 25 for c in chunks)


def test_long_sentence_split_on_word_boundary():
    text = "word " * 50  # one very long "sentence", 250 chars
    chunks = chunk_text(text.strip(), max_chars=40)
    assert all(len(c) <= 40 for c in chunks)
    # No word is ever broken: rejoining yields only whole "word" tokens.
    assert all(tok == "word" for c in chunks for tok in c.split())


def test_whitespace_is_normalized():
    assert chunk_text("Hello\n\n  world.") == ["Hello world."]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chunk.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.chunk'`.

- [ ] **Step 3: Implement `pipeline/chunk.py`**

```python
"""Split chapter text into TTS-sized chunks on sentence boundaries."""
import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _hard_split(sentence: str, max_chars: int) -> list[str]:
    pieces, piece = [], ""
    for word in sentence.split(" "):
        if piece and len(piece) + 1 + len(word) > max_chars:
            pieces.append(piece)
            piece = word
        else:
            piece = f"{piece} {word}".strip()
    if piece:
        pieces.append(piece)
    return pieces


def chunk_text(text: str, max_chars: int = 400) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_SPLIT.split(text):
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(sentence, max_chars))
        elif current and len(current) + 1 + len(sentence) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chunk.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/chunk.py tests/test_chunk.py
git commit -m "feat: sentence-aware text chunking for TTS"
```

---

## Task 4: Synthesis wrapper and audio helpers (`pipeline/synth.py`)

**Files:**
- Create: `pipeline/synth.py`
- Test: `tests/test_synth.py`

Note: the GPU/model code (`Synthesizer`) is covered by an opt-in smoke test that is skipped unless `RUN_KOKORO=1`. The pure audio helper `concat_with_gaps` and the `PRESET_VOICES` table are unit-tested normally.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_synth.py`:

```python
import os
import numpy as np
import pytest

from pipeline.synth import SAMPLE_RATE, PRESET_VOICES, concat_with_gaps


def test_sample_rate_is_24000():
    assert SAMPLE_RATE == 24000


def test_preset_voices_lang_codes_match_prefix():
    assert PRESET_VOICES["af_heart"] == "a"
    assert PRESET_VOICES["bf_emma"] == "b"
    # Every voice's lang_code equals the first letter of its id.
    assert all(lang == vid[0] for vid, lang in PRESET_VOICES.items())


def test_concat_with_gaps_empty():
    out = concat_with_gaps([])
    assert isinstance(out, np.ndarray)
    assert out.shape == (0,)


def test_concat_with_gaps_inserts_silence_between():
    a = np.ones(100, dtype=np.float32)
    b = np.ones(200, dtype=np.float32)
    gap_samples = int(0.5 * SAMPLE_RATE)
    out = concat_with_gaps([a, b], gap_seconds=0.5)
    assert out.shape[0] == 100 + gap_samples + 200
    # The gap region between the two clips is silent.
    assert np.all(out[100:100 + gap_samples] == 0.0)


def test_concat_with_gaps_single_array_no_gap():
    a = np.ones(50, dtype=np.float32)
    assert concat_with_gaps([a], gap_seconds=0.5).shape[0] == 50


@pytest.mark.skipif(os.environ.get("RUN_KOKORO") != "1",
                    reason="Set RUN_KOKORO=1 to run the GPU model smoke test")
def test_synthesizer_smoke():
    from pipeline.synth import Synthesizer
    synth = Synthesizer(voice="af_heart", lang_code="a")
    audio = synth.synth_chunk("Hello, this is a test.")
    assert isinstance(audio, np.ndarray)
    assert audio.shape[0] > SAMPLE_RATE // 4  # at least ~0.25s of audio
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_synth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.synth'` (smoke test reports SKIPPED).

- [ ] **Step 3: Implement `pipeline/synth.py`**

```python
"""Kokoro-based synthesis and audio assembly helpers."""
import numpy as np

SAMPLE_RATE = 24000

# voice_id -> lang_code (lang_code must match the voice's language prefix).
PRESET_VOICES: dict[str, str] = {
    # American English — female
    "af_heart": "a", "af_bella": "a", "af_nicole": "a", "af_sarah": "a", "af_sky": "a",
    # American English — male
    "am_michael": "a", "am_adam": "a", "am_echo": "a", "am_liam": "a",
    # British English — female
    "bf_emma": "b", "bf_isabella": "b", "bf_alice": "b",
    # British English — male
    "bm_george": "b", "bm_lewis": "b", "bm_daniel": "b",
}


def concat_with_gaps(audio_arrays, gap_seconds: float = 0.3, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    arrays = [a for a in audio_arrays if a is not None and len(a) > 0]
    if not arrays:
        return np.zeros(0, dtype=np.float32)
    gap = np.zeros(int(gap_seconds * sample_rate), dtype=np.float32)
    out = []
    for i, a in enumerate(arrays):
        if i:
            out.append(gap)
        out.append(np.asarray(a, dtype=np.float32))
    return np.concatenate(out)


class Synthesizer:
    def __init__(self, voice: str = "af_heart", lang_code: str = "a",
                 device: str = "cuda", speed: float = 1.0):
        from kokoro import KPipeline
        self.pipeline = KPipeline(lang_code=lang_code, device=device)
        self.voice = voice
        self.speed = speed

    def synth_chunk(self, text: str) -> np.ndarray:
        parts = [audio for _, _, audio in self.pipeline(text, voice=self.voice, speed=self.speed)]
        return concat_with_gaps(parts, gap_seconds=0.0)

    def synth_chunks(self, chunks, progress=None) -> np.ndarray:
        out = []
        for i, chunk in enumerate(chunks):
            audio = None
            for _attempt in range(2):  # one retry
                try:
                    audio = self.synth_chunk(chunk)
                    break
                except Exception:
                    audio = None
            if audio is not None and len(audio) > 0:
                out.append(audio)
            if progress is not None:
                progress(i + 1, len(chunks))
        return concat_with_gaps(out, gap_seconds=0.3)

    def preview(self, text: str = "This is a sample of the selected narrator voice.") -> np.ndarray:
        return self.synth_chunk(text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synth.py -v`
Expected: PASS for the 5 unit tests; `test_synthesizer_smoke` SKIPPED.

- [ ] **Step 5 (optional, requires GPU + espeak-ng): Run the real model smoke test**

Run (PowerShell): `$env:RUN_KOKORO=1; pytest tests/test_synth.py::test_synthesizer_smoke -v; Remove-Item Env:RUN_KOKORO`
Expected: PASS (downloads the model on first run; produces audio).

- [ ] **Step 6: Commit**

```bash
git add pipeline/synth.py tests/test_synth.py
git commit -m "feat: Kokoro synthesizer wrapper and audio concat helpers"
```

---

## Task 5: M4B assembly (`pipeline/assemble.py`)

**Files:**
- Create: `pipeline/assemble.py`
- Test: `tests/test_assemble.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_assemble.py`:

```python
import json
import shutil
import subprocess

import numpy as np
import pytest

from pipeline.assemble import write_wav, build_m4b, _build_ffmetadata
from pipeline.synth import SAMPLE_RATE

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def test_ffmetadata_has_chapters_and_escapes():
    meta = _build_ffmetadata(["Intro", "Chap=Two"], [1000, 2000],
                             book_title="My Book", author="Me")
    assert ";FFMETADATA1" in meta
    assert "title=My Book" in meta
    assert meta.count("[CHAPTER]") == 2
    assert "START=0" in meta and "END=1000" in meta
    assert "START=1000" in meta and "END=3000" in meta
    assert "Chap\\=Two" in meta  # '=' escaped


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_build_m4b_produces_two_chapters(tmp_path):
    wav1 = str(tmp_path / "c1.wav")
    wav2 = str(tmp_path / "c2.wav")
    write_wav(np.zeros(SAMPLE_RATE, dtype=np.float32), wav1)        # 1.0s
    write_wav(np.zeros(SAMPLE_RATE // 2, dtype=np.float32), wav2)   # 0.5s
    out = str(tmp_path / "book.m4b")

    build_m4b([("Chapter One", wav1), ("Chapter Two", wav2)], out,
              book_title="Test Book", author="Tester")

    probe = subprocess.run(
        ["ffprobe", "-print_format", "json", "-show_chapters", out],
        capture_output=True, text=True, check=True)
    chapters = json.loads(probe.stdout)["chapters"]
    assert len(chapters) == 2
    assert chapters[0]["tags"]["title"] == "Chapter One"
    assert chapters[1]["tags"]["title"] == "Chapter Two"


def test_build_m4b_missing_ffmpeg_raises(tmp_path):
    with pytest.raises(RuntimeError):
        build_m4b([("A", "x.wav")], str(tmp_path / "o.m4b"),
                  ffmpeg="definitely-not-ffmpeg-xyz")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_assemble.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.assemble'`.

- [ ] **Step 3: Implement `pipeline/assemble.py`**

```python
"""Assemble per-chapter WAVs into a chaptered .m4b with ffmpeg."""
import os
import shutil
import subprocess

import soundfile as sf

from pipeline.synth import SAMPLE_RATE


def write_wav(audio, path: str, sample_rate: int = SAMPLE_RATE) -> str:
    sf.write(path, audio, sample_rate)
    return path


def _duration_ms(wav_path: str) -> int:
    info = sf.info(wav_path)
    return int(round(info.frames / info.samplerate * 1000))


def _escape(value: str) -> str:
    # Escape ffmetadata special characters.
    for ch in ("\\", "=", ";", "#", "\n"):
        value = value.replace(ch, "\\" + ch)
    return value


def _build_ffmetadata(titles, durations_ms, book_title=None, author=None) -> str:
    lines = [";FFMETADATA1"]
    if book_title:
        lines.append(f"title={_escape(book_title)}")
    if author:
        lines.append(f"artist={_escape(author)}")
    start = 0
    for title, dur in zip(titles, durations_ms):
        end = start + dur
        lines += ["", "[CHAPTER]", "TIMEBASE=1/1000",
                  f"START={start}", f"END={end}", f"title={_escape(title)}"]
        start = end
    return "\n".join(lines) + "\n"


def build_m4b(chapter_wavs, output_path: str, book_title=None, author=None,
              cover=None, ffmpeg: str = "ffmpeg") -> str:
    if shutil.which(ffmpeg) is None:
        raise RuntimeError(
            f"'{ffmpeg}' not found. Install ffmpeg and ensure it is on PATH "
            "(see README).")

    titles = [t for t, _ in chapter_wavs]
    paths = [p for _, p in chapter_wavs]
    durations = [_duration_ms(p) for p in paths]

    workdir = os.path.dirname(os.path.abspath(output_path)) or "."
    concat_path = os.path.join(workdir, "_concat.txt")
    meta_path = os.path.join(workdir, "_ffmeta.txt")

    with open(concat_path, "w", encoding="utf-8") as f:
        for p in paths:
            safe = os.path.abspath(p).replace("'", r"'\''")
            f.write(f"file '{safe}'\n")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(_build_ffmetadata(titles, durations, book_title, author))

    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
           "-i", meta_path]
    if cover:
        cmd += ["-i", cover]
    cmd += ["-map", "0:a", "-map_metadata", "1"]
    if cover:
        cmd += ["-map", "2:v", "-disposition:v", "attached_pic", "-c:v", "mjpeg"]
    cmd += ["-c:a", "aac", "-b:a", "64k", output_path]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    finally:
        for tmp in (concat_path, meta_path):
            if os.path.exists(tmp):
                os.remove(tmp)
    return output_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_assemble.py -v`
Expected: PASS for `test_ffmetadata_has_chapters_and_escapes` and `test_build_m4b_missing_ffmpeg_raises`. `test_build_m4b_produces_two_chapters` PASSES if ffmpeg is installed, otherwise SKIPPED. (If skipped, install ffmpeg per the README and re-run to confirm PASS.)

- [ ] **Step 5: Commit**

```bash
git add pipeline/assemble.py tests/test_assemble.py
git commit -m "feat: ffmpeg M4B assembly with chapter markers and metadata"
```

---

## Task 6: Gradio app wiring (`app.py`)

**Files:**
- Create: `app.py`
- Create: `samples/sample_book.txt`

This task is integration glue over already-tested modules, so it is verified by a manual run rather than unit tests.

- [ ] **Step 1: Create a tiny demo book**

Create `samples/sample_book.txt`:

```
## The Beginning
It was a calm morning. The sun rose over the quiet hills, and the village began to stir.

## The Middle
By noon the market was busy. Traders called out their prices while children chased each other between the stalls.

## The End
As night fell, the lanterns were lit one by one, and the village settled into a peaceful sleep.
```

- [ ] **Step 2: Implement `app.py`**

```python
"""Local Gradio web app: plain-text book -> chaptered .m4b audiobook."""
import os

import gradio as gr

from pipeline.parse import parse_chapters
from pipeline.chunk import chunk_text
from pipeline.synth import Synthesizer, PRESET_VOICES, SAMPLE_RATE
from pipeline.assemble import write_wav, build_m4b

OUTPUT_DIR = "output"


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def detect_chapters(txt_file, marker, book_title):
    if txt_file is None:
        return [["(upload a .txt file first)"]]
    chapters = parse_chapters(_read_text(txt_file), marker=marker or "## ",
                              default_title=book_title or "Audiobook")
    if not chapters:
        return [["(no text found)"]]
    return [[i + 1, c.title, len(c.text)] for i, c in enumerate(chapters)]


def preview_voice(voice):
    synth = Synthesizer(voice=voice, lang_code=PRESET_VOICES[voice])
    return (SAMPLE_RATE, synth.preview())


def generate(txt_file, voice, book_title, author, cover, speed, marker,
             progress=gr.Progress()):
    if txt_file is None:
        raise gr.Error("Please upload a .txt file first.")
    chapters = parse_chapters(_read_text(txt_file), marker=marker or "## ",
                              default_title=book_title or "Audiobook")
    if not chapters:
        raise gr.Error("No readable text found in the file.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    synth = Synthesizer(voice=voice, lang_code=PRESET_VOICES[voice],
                        speed=float(speed))

    chapter_wavs = []
    for ci, ch in enumerate(chapters):
        progress(ci / len(chapters), desc=f"Chapter {ci + 1}/{len(chapters)}: {ch.title}")
        audio = synth.synth_chunks(chunk_text(ch.text))
        wav_path = os.path.join(OUTPUT_DIR, f"chapter_{ci + 1:03d}.wav")
        write_wav(audio, wav_path)
        chapter_wavs.append((ch.title, wav_path))

    safe_name = (book_title or "audiobook").strip().replace(" ", "_") or "audiobook"
    out_path = os.path.join(OUTPUT_DIR, f"{safe_name}.m4b")
    progress(0.99, desc="Assembling M4B...")
    build_m4b(chapter_wavs, out_path, book_title=book_title or None,
              author=author or None, cover=cover)
    return out_path


VOICE_CHOICES = list(PRESET_VOICES.keys())

with gr.Blocks(title="Text2Audio") as demo:
    gr.Markdown("# Text2Audio\nTurn a plain-text book into a chaptered audiobook (.m4b).")
    with gr.Row():
        with gr.Column():
            txt_file = gr.File(label="Book (.txt)", file_types=[".txt"], type="filepath")
            voice = gr.Dropdown(VOICE_CHOICES, value="af_heart", label="Narrator voice")
            preview_btn = gr.Button("Preview voice")
            preview_audio = gr.Audio(label="Voice preview")
            book_title = gr.Textbox(label="Book title (optional)")
            author = gr.Textbox(label="Author (optional)")
            cover = gr.Image(label="Cover (optional)", type="filepath")
            speed = gr.Slider(0.5, 1.5, value=1.0, step=0.05, label="Speaking speed")
            marker = gr.Textbox(value="## ", label="Chapter marker prefix")
        with gr.Column():
            detect_btn = gr.Button("Detect chapters")
            chapters_table = gr.Dataframe(headers=["#", "Title", "Chars"],
                                          label="Detected chapters", interactive=False)
            generate_btn = gr.Button("Generate Audiobook", variant="primary")
            result = gr.File(label="Your audiobook (.m4b)")

    preview_btn.click(preview_voice, inputs=voice, outputs=preview_audio)
    detect_btn.click(detect_chapters, inputs=[txt_file, marker, book_title],
                     outputs=chapters_table)
    generate_btn.click(
        generate,
        inputs=[txt_file, voice, book_title, author, cover, speed, marker],
        outputs=result)

if __name__ == "__main__":
    demo.launch(inbrowser=True)
```

- [ ] **Step 3: Manual smoke test — chapter detection (no GPU needed)**

Run: `python -c "from app import detect_chapters; print(detect_chapters('samples/sample_book.txt', '## ', 'Demo'))"`
Expected: a 3-row list — `[[1, 'The Beginning', ...], [2, 'The Middle', ...], [3, 'The End', ...]]`.

- [ ] **Step 4: Manual end-to-end run (requires GPU + espeak-ng + ffmpeg)**

Run: `python app.py`
Then in the browser: upload `samples/sample_book.txt`, click **Detect chapters** (confirm 3 rows), click **Preview voice** (hear a sample), click **Generate Audiobook**.
Expected: progress shows "Chapter 1/3 …" through 3/3, then an `output/Demo.m4b` (or `audiobook.m4b`) download appears. Verify chapters: `ffprobe -show_chapters output/audiobook.m4b` lists 3 chapters with the correct titles.

- [ ] **Step 5: Commit**

```bash
git add app.py samples/sample_book.txt
git commit -m "feat: Gradio UI wiring the parse->synth->assemble pipeline"
```

---

## Task 7: README and setup docs

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

````markdown
# Text2Audio

Turn a plain-text book into a natural-sounding, chaptered `.m4b` audiobook —
free and fully local, using the Kokoro-82M TTS model on your GPU.

## Requirements

- Windows (tested) with an NVIDIA GPU + recent driver
- Python 3.10–3.12
- [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) on your PATH (provides `ffmpeg` and `ffprobe`)
- [espeak-ng](https://github.com/espeak-ng/espeak-ng/releases) (install the Windows `.msi`)

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --index-url https://download.pytorch.org/whl/cu124 torch
pip install -r requirements.txt
```

If espeak-ng is not auto-detected, set:

```powershell
setx PHONEMIZER_ESPEAK_LIBRARY "C:\Program Files\eSpeak NG\libespeak-ng.dll"
setx PHONEMIZER_ESPEAK_PATH "C:\Program Files\eSpeak NG\espeak-ng.exe"
```

## Run

```powershell
python app.py
```

Your browser opens the app. Upload a `.txt` book, pick a voice, optionally set
title/author/cover, click **Detect chapters** to confirm the split, then
**Generate Audiobook**. The finished `.m4b` lands in `output/`.

## Chapter markers

Best results: put a marker line before each chapter using the prefix `## `:

```
## Chapter One
Once upon a time...

## Chapter Two
...
```

If you don't add markers, the app auto-detects `Chapter N` and ALL-CAPS heading
lines. If it finds none, the whole book becomes one chapter.

## Voices

Built-in Kokoro narrators (American `af_*`/`am_*`, British `bf_*`/`bm_*`).
`af_heart` is a great default. Use **Preview voice** to audition.

## Tests

```powershell
pytest -q
```

GPU model tests are opt-in: `$env:RUN_KOKORO=1; pytest tests/test_synth.py`.

## License

Uses Kokoro-82M (Apache-2.0).
````

- [ ] **Step 2: Verify the full unit suite passes**

Run: `pytest -q`
Expected: all unit tests PASS; GPU/ffmpeg-dependent tests SKIPPED if those tools are absent.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: setup, usage, and chapter-marker instructions"
```

---

## Self-review notes (addressed)

- **Spec coverage:** parse (Task 2), chunk (Task 3), synth + resilience/retry (Task 4), per-chapter stitch + M4B markers/metadata/cover (Task 5), Gradio UI with preview + detected-chapters preview + progress (Task 6), error handling for missing ffmpeg (Task 5) and empty/no-chapter input (Tasks 2 & 6), README incl. how to add markers (Task 7). All spec sections map to a task.
- **Type consistency:** `Chapter(title, text)`, `parse_chapters(text, marker, default_title)`, `chunk_text(text, max_chars)`, `Synthesizer(...).synth_chunks/synth_chunk/preview`, `concat_with_gaps`, `write_wav`, `build_m4b(chapter_wavs, output_path, ...)`, `SAMPLE_RATE=24000`, `PRESET_VOICES` — names/signatures used identically across Tasks 4–6.
- **No placeholders:** every code and test step contains complete, runnable content.
- **Out of scope (per spec):** voice cloning, non-txt inputs, per-character voices — intentionally omitted.
```
