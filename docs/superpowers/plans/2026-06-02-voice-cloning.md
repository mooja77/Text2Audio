# Voice Cloning (F5-TTS) Implementation Plan (Phase 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users narrate in a cloned voice — upload a reference clip, save it as a named voice, and select it like a built-in narrator — powered by a local, opt-in F5-TTS engine while Kokoro stays the fast default.

**Architecture:** Refactor the synthesizer into a `BaseSynthesizer` (engine-agnostic gap/paragraph logic) with Kokoro and a new F5-TTS `ClonedSynthesizer` as subclasses. A `VoiceStore` persists uploaded reference clips. A `resolve_synth(voice_id, speed)` factory picks the engine by voice id; render/preview/UI thread cloned voices alongside presets. F5 is a heavy, lazily-imported optional dependency.

**Tech Stack:** Python 3.11, F5-TTS (`f5-tts`, optional), the existing kokoro/ffmpeg/FastAPI pipeline, pytest (GPU-free via mocked engines), vanilla JS frontend.

---

## Environment notes (already done — do NOT redo)

- venv at `.venv`; use `./.venv/Scripts/python.exe`. ffmpeg on PATH. **Do NOT install `f5-tts` during tasks** — it's heavy/optional and all unit tests mock the cloning engine. It is installed only in the final live-verification task (Task 9), by the controller.
- Branch: create `voice-cloning` off `master` (Task 0). Git identity fallback: `git -c user.name="Text2Audio" -c user.email="mooja77@gmail.com" commit ...`.
- Full suite green before starting (`./.venv/Scripts/python.exe -m pytest -q` → 83 passed, 1 skipped).
- Key existing code: `pipeline/synth.py` (`Synthesizer`, `SAMPLE_RATE`, `SENTENCE_GAP`, `PARAGRAPH_GAP`, `concat_with_gaps`, `PRESET_VOICES`), `backend/render.py` (`render_audiobook`/`_render_into`; currently `synth = synth_factory(voice=voice, lang_code=PRESET_VOICES[voice], speed=float(speed))`), `server.py` (`SYNTH_FACTORY=Synthesizer`, `PRESET_VOICES`, `_check_id`, `voices_payload`, render `target`, `/api/voice-preview`), `backend/library.py` (`new_id`).

## Locked interfaces

- `pipeline/synth.py`: `class BaseSynthesizer` with abstract `synth_chunk(text)->np.ndarray` and concrete `synth_chunks`, `synth_paragraphs`, `preview`; `class Synthesizer(BaseSynthesizer)`.
- `pipeline/clone_synth.py`: `class ClonedSynthesizer(BaseSynthesizer)` (`__init__(ref_wav, ref_text="", speed=1.0)`, `synth_chunk`); `_import_f5()`, `_get_model()`, module `_MODEL`.
- `backend/voices.py`: `class VoiceStore(base_dir)` → `create(name, audio_bytes, src_ext, ref_text="")->dict`, `list()->list[dict]`, `get(id)->dict|None`, `ref_path(id)->str`, `delete(id)->None`; `new_voice_id()->str`.
- `backend/render.py`: `synth_factory(voice_id, speed) -> BaseSynthesizer` contract; default `_default_synth_factory`.
- `server.py`: `voices` global, `resolve_synth(voice_id, speed)`, `SYNTH_FACTORY=resolve_synth`; `POST /api/voices/clone`, `DELETE /api/voices/{id}`; `/api/voices` returns `kind` ("preset"|"cloned").

---

## Task 0: Branch

- [ ] **Step 1:** `git checkout master && git checkout -b voice-cloning && git branch --show-current` → `voice-cloning`.

---

## Task 1: Refactor synth into `BaseSynthesizer`

**Files:** Modify `pipeline/synth.py`; modify `tests/test_synth.py`

- [ ] **Step 1: Add the failing test** — append to `tests/test_synth.py`:

```python
def test_base_synthesizer_provides_paragraph_logic():
    from pipeline.synth import BaseSynthesizer

    class Tiny(BaseSynthesizer):
        def synth_chunk(self, text):
            return np.ones(100, dtype=np.float32)

    s = Tiny()
    # one paragraph, two chunks -> 100 + SENTENCE_GAP + 100
    from pipeline.synth import SENTENCE_GAP
    out = s.synth_paragraphs([["a", "b"]])
    assert out.shape[0] == 100 + int(SENTENCE_GAP * SAMPLE_RATE) + 100
    # preview uses synth_chunk
    assert s.preview("hi").shape[0] == 100


def test_kokoro_synthesizer_is_base_subclass():
    from pipeline.synth import Synthesizer, BaseSynthesizer
    assert issubclass(Synthesizer, BaseSynthesizer)
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_synth.py -k "base or subclass" -v` → FAIL (no `BaseSynthesizer`).

- [ ] **Step 3: Refactor `pipeline/synth.py`.** Replace the entire `class Synthesizer:` definition (the class and all its methods `__init__`, `synth_chunk`, `synth_chunks`, `synth_paragraphs`, `preview`) with:

```python
class BaseSynthesizer:
    """Engine-agnostic synthesis: subclasses implement synth_chunk(text)."""

    def synth_chunk(self, text: str) -> np.ndarray:
        raise NotImplementedError

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

    def preview(self, text: str = "This is a sample of the selected narrator voice.") -> np.ndarray:
        return self.synth_chunk(text)


class Synthesizer(BaseSynthesizer):
    def __init__(self, voice: str = "af_heart", lang_code: str = "a",
                 device: str = "cuda", speed: float = 1.0):
        from kokoro import KPipeline
        self.pipeline = KPipeline(lang_code=lang_code, device=device)
        self.voice = voice
        self.speed = speed

    def synth_chunk(self, text: str) -> np.ndarray:
        parts = [audio for _, _, audio in self.pipeline(text, voice=self.voice, speed=self.speed)]
        return concat_with_gaps(parts, gap_seconds=0.0)
```

(Keep the module constants `SAMPLE_RATE`, `SENTENCE_GAP`, `PARAGRAPH_GAP`, `PRESET_VOICES`, and `concat_with_gaps` exactly as they are — only the class is restructured.)

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_synth.py -v` → all pass (existing tests + 2 new; GPU smoke still SKIPPED).

- [ ] **Step 5: Commit** — `git add pipeline/synth.py tests/test_synth.py && git commit -m "refactor: extract BaseSynthesizer (engine-agnostic synthesis)"`

---

## Task 2: F5-TTS cloned synthesizer

**Files:** Create `pipeline/clone_synth.py`, `tests/test_clone_synth.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_clone_synth.py`:

```python
import numpy as np
import pytest

from pipeline.clone_synth import ClonedSynthesizer, _get_model
import pipeline.clone_synth as cs
from pipeline.synth import BaseSynthesizer, SAMPLE_RATE, SENTENCE_GAP


def test_cloned_is_base_synthesizer():
    assert issubclass(ClonedSynthesizer, BaseSynthesizer)


def test_paragraph_logic_inherited(monkeypatch):
    s = ClonedSynthesizer.__new__(ClonedSynthesizer)  # bypass model load
    monkeypatch.setattr(s, "synth_chunk", lambda t: np.ones(100, dtype=np.float32))
    out = s.synth_paragraphs([["a", "b"]])
    assert out.shape[0] == 100 + int(SENTENCE_GAP * SAMPLE_RATE) + 100


def test_missing_f5_raises_clear_error(monkeypatch):
    cs._MODEL = None
    def boom():
        raise ImportError("no f5")
    monkeypatch.setattr(cs, "_import_f5", boom)
    with pytest.raises(RuntimeError, match="f5-tts"):
        _get_model()


def test_resample_changes_length():
    out = cs._resample(np.ones(1000, dtype=np.float32), 16000, 24000)
    assert out.shape[0] == 1500


@pytest.mark.skipif(__import__("os").environ.get("RUN_F5") != "1",
                    reason="Set RUN_F5=1 to run the F5 model smoke test")
def test_f5_smoke(tmp_path):
    # requires f5-tts installed + a reference wav; controller runs this live
    import soundfile as sf
    ref = str(tmp_path / "ref.wav")
    sf.write(ref, np.zeros(SAMPLE_RATE, dtype=np.float32), SAMPLE_RATE)
    s = ClonedSynthesizer(ref, ref_text="", speed=1.0)
    audio = s.synth_chunk("Hello there, this is a test.")
    assert isinstance(audio, np.ndarray) and audio.shape[0] > 0
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_clone_synth.py -v` → FAIL (no module). (`test_f5_smoke` SKIPPED.)

- [ ] **Step 3: Implement `pipeline/clone_synth.py`:**

```python
"""F5-TTS voice-cloning synthesizer (heavy, optional, lazily imported)."""
import numpy as np

from pipeline.synth import BaseSynthesizer, SAMPLE_RATE

_MODEL = None


def _import_f5():
    from f5_tts.api import F5TTS
    return F5TTS


def _get_model():
    global _MODEL
    if _MODEL is None:
        try:
            F5TTS = _import_f5()
        except Exception as exc:  # not installed / import failure
            raise RuntimeError("install f5-tts to use cloned voices") from exc
        _MODEL = F5TTS()
    return _MODEL


def _resample(wav: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return np.asarray(wav, dtype=np.float32)
    n_out = int(round(len(wav) * sr_out / sr_in))
    x = np.linspace(0, len(wav), n_out, endpoint=False)
    return np.interp(x, np.arange(len(wav)), wav).astype(np.float32)


class ClonedSynthesizer(BaseSynthesizer):
    def __init__(self, ref_wav: str, ref_text: str = "", speed: float = 1.0):
        self.ref_wav = ref_wav
        self.ref_text = ref_text or ""
        self.speed = float(speed)
        self._model = _get_model()

    def synth_chunk(self, text: str) -> np.ndarray:
        wav, sr, _ = self._model.infer(
            ref_file=self.ref_wav, ref_text=self.ref_text,
            gen_text=text, speed=self.speed)
        return _resample(np.asarray(wav, dtype=np.float32), sr, SAMPLE_RATE)
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_clone_synth.py -v` → 4 passed, 1 skipped.

- [ ] **Step 5: Commit** — `git add pipeline/clone_synth.py tests/test_clone_synth.py && git commit -m "feat: F5-TTS cloned synthesizer (lazy/optional)"`

---

## Task 3: Cloned-voice store

**Files:** Create `backend/voices.py`, `tests/test_voices_store.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_voices_store.py`:

```python
import os
import numpy as np
import soundfile as sf
import pytest

from backend.voices import VoiceStore, new_voice_id


def _wav_bytes(tmp_path):
    p = tmp_path / "src.wav"
    sf.write(str(p), np.zeros(16000, dtype=np.float32), 16000)  # 1s @16k mono
    return p.read_bytes()


def test_new_voice_id_unique():
    assert new_voice_id() != new_voice_id()


def test_create_list_get_delete(tmp_path):
    store = VoiceStore(str(tmp_path / "voices"))
    assert store.list() == []
    v = store.create("My Voice", _wav_bytes(tmp_path), ".wav", ref_text="hello")
    assert v["name"] == "My Voice" and v["refText"] == "hello"
    # sample.wav exists and is 24 kHz mono
    rp = store.ref_path(v["id"])
    assert os.path.isfile(rp)
    info = sf.info(rp)
    assert info.samplerate == 24000 and info.channels == 1
    assert [x["id"] for x in store.list()] == [v["id"]]
    assert store.get(v["id"])["name"] == "My Voice"
    store.delete(v["id"])
    assert store.get(v["id"]) is None


def test_create_rejects_unreadable_audio(tmp_path):
    store = VoiceStore(str(tmp_path / "voices"))
    with pytest.raises(ValueError):
        store.create("Bad", b"not audio at all", ".wav", ref_text="")
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_voices_store.py -v` → FAIL.

- [ ] **Step 3: Implement `backend/voices.py`:**

```python
"""Persistent store of user-cloned voices (reference clip + metadata)."""
import datetime
import json
import os
import shutil
import subprocess
import tempfile
import uuid

SAMPLE_NAME = "sample.wav"
META_NAME = "meta.json"


def new_voice_id() -> str:
    return "v" + uuid.uuid4().hex[:9]


class VoiceStore:
    def __init__(self, base_dir: str):
        self.base = base_dir
        os.makedirs(self.base, exist_ok=True)

    def _dir(self, id: str) -> str:
        return os.path.join(self.base, id)

    def ref_path(self, id: str) -> str:
        return os.path.join(self._dir(id), SAMPLE_NAME)

    def get(self, id: str) -> dict | None:
        p = os.path.join(self._dir(id), META_NAME)
        if not os.path.isfile(p):
            return None
        with open(p, "r", encoding="utf-8") as f:
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

    def delete(self, id: str) -> None:
        shutil.rmtree(self._dir(id), ignore_errors=True)

    def create(self, name: str, audio_bytes: bytes, src_ext: str, ref_text: str = "") -> dict:
        vid = new_voice_id()
        d = self._dir(vid)
        os.makedirs(d, exist_ok=True)
        src = os.path.join(d, "_src" + (src_ext if src_ext.startswith(".") else ".bin"))
        with open(src, "wb") as f:
            f.write(audio_bytes)
        out = self.ref_path(vid)
        # Convert to clean mono 24 kHz wav for F5; raise on undecodable input.
        try:
            subprocess.run(["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", "24000", out],
                           check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            shutil.rmtree(d, ignore_errors=True)
            raise ValueError("could not read that audio file") from exc
        finally:
            if os.path.exists(src):
                os.remove(src)
        manifest = {"id": vid, "name": name, "refText": ref_text or "",
                    "created": datetime.datetime.now().isoformat(timespec="seconds")}
        with open(os.path.join(d, META_NAME), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        return manifest
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_voices_store.py -v` → 3 passed. (Real ffmpeg converts the fixture and rejects the garbage bytes.)

- [ ] **Step 5: Commit** — `git add backend/voices.py tests/test_voices_store.py && git commit -m "feat: cloned-voice store (ffmpeg-normalized reference)"`

---

## Task 4: Record the f5-tts dependency

**Files:** Modify `requirements.txt`

- [ ] **Step 1: Append to `requirements.txt`:**

```
f5-tts>=1.1  # optional: only needed for voice cloning (heavy GPU dependency)
```

- [ ] **Step 2: Confirm nothing imports it at startup** — `./.venv/Scripts/python.exe -c "import server; print('server imports without f5-tts:', 'f5_tts' not in __import__('sys').modules)"` → prints `True`.

- [ ] **Step 3: Commit** — `git add requirements.txt && git commit -m "chore: add optional f5-tts dependency"`

---

## Task 5: Engine-agnostic render factory

**Files:** Modify `backend/render.py`; modify `tests/test_render.py`

- [ ] **Step 1: Update the test fakes + add a cloned-voice render test** in `tests/test_render.py`.

(a) Replace the existing `FakeSynth` class (constructor `(voice, lang_code, speed=1.0)`) with a factory matching the new `(voice_id, speed)` contract:

```python
class FakeSynth:
    def __init__(self, voice_id, speed=1.0):
        self.voice = voice_id
    def synth_chunks(self, chunks, progress=None):
        return np.zeros(int(0.2 * SAMPLE_RATE) * max(1, len(chunks)), dtype=np.float32)
    def synth_paragraphs(self, paragraphs, progress=None):
        n = sum(len(p) for p in paragraphs)
        return np.zeros(int(0.2 * SAMPLE_RATE) * max(1, n), dtype=np.float32)
```

(b) `FakeSynthP(FakeSynth)` stays as-is (`pass`).

(c) Append this test:

```python
def test_render_factory_called_with_voice_and_speed(tmp_path):
    lib = Library(str(tmp_path))
    seen = {}

    def factory(voice_id, speed):
        seen["voice"], seen["speed"] = voice_id, speed
        return FakeSynth(voice_id, speed)

    render_audiobook(book_text="## A\n\nHello.", voice="my_clone", speed=0.9, title="T",
                     author="", cover_path=None, library=lib, job_id="jf",
                     emit=lambda e: None, synth_factory=factory)
    assert seen == {"voice": "my_clone", "speed": 0.9}
    assert lib.get("jf")["voice"] == "my_clone"
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_render.py -v` → FAILs (old fakes/call signature mismatch).

- [ ] **Step 3: Edit `backend/render.py`.**

(a) Add a default factory after the imports (PRESET_VOICES is already imported):

```python
def _default_synth_factory(voice_id, speed):
    return Synthesizer(voice=voice_id, lang_code=PRESET_VOICES[voice_id], speed=float(speed))
```

(b) Change `render_audiobook`'s default. Find:
```python
def render_audiobook(*, book_text, voice, speed, title, author, cover_path,
                     library, job_id, emit, synth_factory=Synthesizer,
                     custom_rules=None) -> dict:
```
Replace with:
```python
def render_audiobook(*, book_text, voice, speed, title, author, cover_path,
                     library, job_id, emit, synth_factory=_default_synth_factory,
                     custom_rules=None) -> dict:
```

(c) In `_render_into`, change the synthesizer construction. Find:
```python
    synth = synth_factory(voice=voice, lang_code=PRESET_VOICES[voice], speed=float(speed))
```
Replace with:
```python
    synth = synth_factory(voice, float(speed))
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_render.py -v` → all pass.

- [ ] **Step 5: Commit** — `git add backend/render.py tests/test_render.py && git commit -m "refactor: render synth_factory(voice_id, speed) contract"`

---

## Task 6: Server — resolution, voices API, clone endpoints

**Files:** Modify `server.py`; modify `tests/test_api.py`

- [ ] **Step 1: Update fakes + add tests** in `tests/test_api.py`.

(a) Replace `_FakeSynth`'s constructor to the new contract and make it usable as a factory:

```python
class _FakeSynth:
    def __init__(self, voice_id, speed=1.0):
        pass
    def synth_chunks(self, chunks, progress=None):
        return np.zeros(int(0.1 * SAMPLE_RATE), dtype=np.float32)
    def synth_paragraphs(self, paragraphs, progress=None):
        return np.zeros(int(0.1 * SAMPLE_RATE), dtype=np.float32)
    def preview(self, text="x"):
        return np.zeros(int(0.1 * SAMPLE_RATE), dtype=np.float32)
```

(b) `_BlockingSynth`'s constructor → `(self, voice_id, speed=1.0)` (drop `lang_code`); keep its `synth_chunks`; add a `synth_paragraphs` that also `gate.wait(...)` then returns silence. Since the render path uses `synth_paragraphs`, update it:

```python
    class _BlockingSynth:
        def __init__(self, voice_id, speed=1.0):
            pass
        def synth_paragraphs(self, paragraphs, progress=None):
            gate.wait(timeout=5)
            return np.zeros(int(0.1 * SAMPLE_RATE), dtype=np.float32)
```

(c) The tests monkeypatch `server.SYNTH_FACTORY`. The factory is now `(voice_id, speed) -> synth`. A class whose `__init__(voice_id, speed)` returns an instance satisfies this. So `monkeypatch.setattr(server, "SYNTH_FACTORY", _FakeSynth)` still works (calling `_FakeSynth(voice_id, speed)`). Keep those as-is.

(d) Append these tests:

```python
def test_voices_includes_kind(client):
    voices = client.get("/api/voices").json()
    assert all("kind" in v for v in voices)
    assert any(v["id"] == "bm_george" and v["kind"] == "preset" for v in voices)


def _wav_bytes():
    import io, soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, np.zeros(16000, dtype=np.float32), 16000, format="WAV")
    return buf.getvalue()


def test_clone_create_list_delete(client):
    files = {"audio": ("ref.wav", _wav_bytes(), "audio/wav")}
    data = {"name": "Cloney", "refText": "hello there"}
    r = client.post("/api/voices/clone", files=files, data=data)
    assert r.status_code == 200
    vid = r.json()["id"]
    voices = client.get("/api/voices").json()
    cloned = [v for v in voices if v["id"] == vid]
    assert cloned and cloned[0]["kind"] == "cloned" and cloned[0]["name"] == "Cloney"
    assert client.delete(f"/api/voices/{vid}").status_code == 200
    assert not any(v["id"] == vid for v in client.get("/api/voices").json())


def test_clone_rejects_empty_name(client):
    files = {"audio": ("ref.wav", _wav_bytes(), "audio/wav")}
    assert client.post("/api/voices/clone", files=files, data={"name": "  "}).status_code == 400


def test_render_with_cloned_voice(client, monkeypatch):
    import server
    monkeypatch.setattr(server, "SYNTH_FACTORY", _FakeSynth)
    vid = client.post("/api/voices/clone", files={"audio": ("r.wav", _wav_bytes(), "audio/wav")},
                      data={"name": "C"}).json()["id"]
    r = client.post("/api/render", json={"bookText": "## A\n\nhi", "voice": vid, "title": "X"})
    assert r.status_code == 200


def test_render_unknown_voice_still_400(client):
    assert client.post("/api/render", json={"bookText": "## A\n\nhi", "voice": "nope"}).status_code == 400
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -k "voices or clone or cloned or unknown_voice" -v` → FAIL.

- [ ] **Step 3: Edit `server.py`.**

(a) Add imports (near the other backend imports):
```python
from fastapi import Form
from backend.voices import VoiceStore
from pipeline.clone_synth import ClonedSynthesizer
```

(b) Add the store global after the `pron` global:
```python
VOICES_DIR = os.environ.get("T2A_VOICES_DIR", os.path.join(os.path.dirname(LIBRARY_DIR), "voices"))
voices = VoiceStore(VOICES_DIR)
```

(c) Add the resolver + factory hook after `voices_payload` is defined:
```python
def resolve_synth(voice_id, speed):
    if voice_id in PRESET_VOICES:
        return Synthesizer(voice=voice_id, lang_code=PRESET_VOICES[voice_id], speed=float(speed))
    meta = voices.get(voice_id)
    if meta is None:
        raise KeyError(voice_id)
    return ClonedSynthesizer(voices.ref_path(voice_id), meta.get("refText", ""), float(speed))


SYNTH_FACTORY = resolve_synth
```
Remove the old `SYNTH_FACTORY = Synthesizer` line.

(d) Update `voices_payload` to include cloned voices and a `kind`. Replace the existing function body so it returns presets tagged `kind:"preset"` plus cloned voices:
```python
def voices_payload() -> list[dict]:
    out = []
    for vid, lang in PRESET_VOICES.items():
        out.append({"id": vid, "label": _VOICE_LABELS.get(vid, vid),
                    "accent": _ACCENT.get(lang, lang),
                    "gender": "Female" if vid[1] == "f" else "Male", "kind": "preset"})
    for v in voices.list():
        out.append({"id": v["id"], "label": v["name"], "name": v["name"],
                    "accent": "Cloned", "gender": "", "kind": "cloned"})
    return out
```

(e) Update the render `target` + the unknown-voice guard in `start_render`. Find:
```python
    if req.voice not in PRESET_VOICES:
        raise HTTPException(status_code=400, detail="unknown voice")
```
Replace with:
```python
    if req.voice not in PRESET_VOICES and voices.get(req.voice) is None:
        raise HTTPException(status_code=400, detail="unknown voice")
```
And the `target`'s render call already passes `synth_factory=SYNTH_FACTORY`; since render now calls `synth_factory(voice, speed)` and `SYNTH_FACTORY` is `resolve_synth`, no change needed there — but confirm the render call still reads `synth_factory=SYNTH_FACTORY`.

(f) Update `/api/voice-preview` to use the resolver. Find its body that builds `synth = SYNTH_FACTORY(voice=req.voice, lang_code=PRESET_VOICES[req.voice])` and replace the construction with:
```python
    if req.voice not in PRESET_VOICES and voices.get(req.voice) is None:
        raise HTTPException(status_code=400, detail="unknown voice")
    synth = SYNTH_FACTORY(req.voice, 1.0)
```
(keep the rest: `audio = synth.preview(...)`/`synth_chunks`, write WAV, return Response).

(g) Add the clone endpoints immediately BEFORE the `# IMPORTANT: keep this static mount` comment:
```python
@app.post("/api/voices/clone")
async def voices_clone(name: str = Form(...), audio: UploadFile = File(...),
                       refText: str = Form("")):
    if not name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="audio is required")
    ext = os.path.splitext(audio.filename or "")[1] or ".wav"
    try:
        return voices.create(name.strip(), data, ext, refText.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/voices/{id}")
def voices_delete(id: str):
    _check_id(id[1:] if id.startswith("v") else id)  # ids are "v"+hex
    if voices.get(id) is None:
        raise HTTPException(status_code=404, detail="not found")
    voices.delete(id)
    return {"deleted": id}
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v` → all pass.

- [ ] **Step 5: Run the FULL suite** — `./.venv/Scripts/python.exe -m pytest -q` → all pass (1 skipped Kokoro smoke; F5 smoke also skipped). Report the count.

- [ ] **Step 6: Commit** — `git add server.py tests/test_api.py && git commit -m "feat: voice resolution + clone/list/delete endpoints"`

---

## Task 7: Clone UI

**Files:** Modify `web/js/voices.js`, `web/js/create.js`. Verified by serving + controller browser pass.

- [ ] **Step 1: Replace `web/js/voices.js`** with (adds the clone panel + cloned badges/delete; presets unchanged):

```javascript
const Voices = {
  render() {
    const el = document.getElementById("tab-voices");
    el.innerHTML = `
      <h2>Voices</h2>
      <p class="subtitle">Click a voice to hear a sample, then "Use" it in Create.</p>
      <div class="panel" style="max-width:680px;margin-bottom:18px">
        <div class="label">Clone a voice</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <input class="cinput" id="cv-name" placeholder="Voice name (e.g. My Narrator)">
          <input class="cinput" id="cv-file" type="file" accept="audio/*">
        </div>
        <textarea class="cinput" id="cv-text" rows="2" placeholder="(optional) type what's said in the clip — improves quality; leave blank to auto-detect"></textarea>
        <button class="btn" id="cv-add" style="margin-top:8px">Create voice</button>
        <div class="muted" style="font-size:12px;margin-top:6px">Upload ~10–30s of clean speech. Cloned renders are higher quality but much slower.</div>
      </div>
      <div class="cards" id="vcards"></div>`;
    el.querySelectorAll(".cinput").forEach(i => {
      i.style.cssText = "background:var(--panel2);border:1px solid var(--bd);color:var(--tx);border-radius:8px;padding:9px 10px;font-size:14px;width:100%;margin-top:8px";
    });
    document.getElementById("cv-add").onclick = () => this.clone();
    this.refresh();
  },

  async refresh() {
    try { T2A.state.voices = await T2A.api("/api/voices"); } catch (e) {}
    const cards = document.getElementById("vcards");
    cards.innerHTML = T2A.state.voices.map(v => `
      <div class="vcard ${v.id === T2A.state.voice ? "sel" : ""}" data-v="${T2A.esc(v.id)}">
        <div class="dot"></div>
        <div class="vn">${T2A.esc(v.label)} ${v.kind === "cloned" ? '<span style="font-size:10px;color:var(--ac2)">● cloned</span>' : ""}</div>
        <div class="vm">${T2A.esc(v.accent)}${v.gender ? " · " + T2A.esc(v.gender) : ""}</div>
        <div class="row">
          <button class="btn play" data-v="${T2A.esc(v.id)}">▶ Sample</button>
          <button class="btn use" data-v="${T2A.esc(v.id)}">Use</button>
          ${v.kind === "cloned" ? `<button class="btn del" data-v="${T2A.esc(v.id)}">✕</button>` : ""}
        </div>
      </div>`).join("");
    cards.querySelectorAll(".play").forEach(b => b.onclick = e => { e.stopPropagation(); this.sample(b.dataset.v, b); });
    cards.querySelectorAll(".use").forEach(b => b.onclick = e => {
      e.stopPropagation(); T2A.state.voice = b.dataset.v; T2A.toast("Voice set: " + b.dataset.v); this.refresh(); });
    cards.querySelectorAll(".del").forEach(b => b.onclick = async e => {
      e.stopPropagation();
      if (!confirm("Delete this cloned voice?")) return;
      await T2A.api(`/api/voices/${encodeURIComponent(b.dataset.v)}`, { method: "DELETE" });
      T2A.toast("Deleted"); this.refresh();
    });
  },

  async clone() {
    const name = document.getElementById("cv-name").value.trim();
    const file = document.getElementById("cv-file").files[0];
    const refText = document.getElementById("cv-text").value;
    if (!name || !file) { T2A.toast("Enter a name and choose an audio file"); return; }
    const fd = new FormData();
    fd.append("name", name); fd.append("audio", file); fd.append("refText", refText);
    T2A.toast("Creating voice…");
    try {
      await T2A.api("/api/voices/clone", { method: "POST", body: fd });
      document.getElementById("cv-name").value = ""; document.getElementById("cv-text").value = "";
      T2A.toast("Voice created"); this.refresh();
    } catch (e) { T2A.toast("Clone failed — check the audio file"); }
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

- [ ] **Step 2: Update the voice dropdown in `web/js/create.js`** to group cloned voices. Find:
```javascript
    const voiceOpts = T2A.state.voices.map(v =>
      `<option value="${v.id}" ${v.id === T2A.state.voice ? "selected" : ""}>${v.label} · ${v.accent} ${v.gender}</option>`).join("");
```
Replace with:
```javascript
    const opt = v => `<option value="${T2A.esc(v.id)}" ${v.id === T2A.state.voice ? "selected" : ""}>${T2A.esc(v.label)}${v.kind === "cloned" ? " (cloned)" : ` · ${T2A.esc(v.accent)} ${T2A.esc(v.gender)}`}</option>`;
    const presets = T2A.state.voices.filter(v => v.kind !== "cloned").map(opt).join("");
    const cloned = T2A.state.voices.filter(v => v.kind === "cloned").map(opt).join("");
    const voiceOpts = presets + (cloned ? `<optgroup label="Your voices">${cloned}</optgroup>` : "");
```

- [ ] **Step 3: Verify it serves** — start the server (no browser) and check the JS loads:

Run (PowerShell): `$env:T2A_NO_BROWSER=1; Start-Process -NoNewWindow ./.venv/Scripts/python.exe server.py; Start-Sleep 3; (Invoke-WebRequest http://127.0.0.1:8765/js/voices.js).StatusCode; (Invoke-WebRequest http://127.0.0.1:8765/api/voices).Content.Contains("preset"); Get-Process python | Stop-Process`
Expected: `200` and `True`.

- [ ] **Step 4: Commit** — `git add web/js/voices.js web/js/create.js && git commit -m "feat: clone-a-voice UI + cloned voices in lists"`

---

## Task 8: Gitignore generated voices

**Files:** Modify `.gitignore`

- [ ] **Step 1:** Append `voices/` to `.gitignore` (runtime user data, like `library/` and `data/`).

- [ ] **Step 2: Commit** — `git add .gitignore && git commit -m "chore: gitignore runtime cloned-voice data"`

---

## Task 9: End-to-end verification (controller, with live F5)

**Files:** none (verification only). The controller installs f5-tts and runs a real clone+render.

- [ ] **Step 1: Full GPU-free suite** — `./.venv/Scripts/python.exe -m pytest -q` → all pass (Kokoro + F5 smokes skipped).

- [ ] **Step 2: Install F5 (controller)** — `./.venv/Scripts/python.exe -m pip install -q f5-tts` (heavy; may take a while). Then `RUN_F5=1` smoke: create a short real reference wav and run `tests/test_clone_synth.py::test_f5_smoke` to confirm the F5 API matches `ClonedSynthesizer.synth_chunk` (fix `clone_synth.py` if the real `F5TTS.infer` signature differs — e.g. arg names or return tuple shape — then re-run).

- [ ] **Step 3: Live clone + render through the server.** Start the server (espeak env), then via the API or Playwright:
  - Create a cloned voice: `POST /api/voices/clone` with a real ~15s speech wav (the controller can synthesize one with Kokoro or use a sample) + a transcript.
  - `GET /api/voices` shows it as `kind:"cloned"`.
  - Preview it: `POST /api/voice-preview {voice:<id>}` returns audible WAV.
  - Render a one-paragraph book with the cloned voice; confirm it completes and the library entry's `voice` is the cloned id, and the audio is non-silent.
  Stop the server.

- [ ] **Step 4: No commit** (verification only). Fix any real-API mismatch in `pipeline/clone_synth.py` (and re-run Step 2) before declaring done.

---

## Self-review notes (addressed)

- **Spec coverage:** BaseSynthesizer refactor (T1), F5 ClonedSynthesizer lazy/optional (T2), VoiceStore + ffmpeg-normalized reference (T3), optional dep (T4), engine-agnostic render factory (T5), resolver + `/api/voices` kind + clone/delete + preview/render wiring + unknown-voice guard (T6), clone UI + grouped dropdown (T7), gitignore (T8), live F5 e2e (T9). All spec sections map to a task.
- **Type/interface consistency:** `BaseSynthesizer.synth_chunk`, `synth_factory(voice_id, speed)`, `resolve_synth`/`SYNTH_FACTORY`, `VoiceStore.create/list/get/ref_path/delete`, `ClonedSynthesizer(ref_wav, ref_text, speed)`, `/api/voices` entries carrying `kind`/`name`, and the UI reading exactly those keys are consistent across tasks. The test fakes are updated to the new `(voice_id, speed)` factory contract in T5 (render) and T6 (api).
- **GPU-free tests:** every unit test mocks or bypasses both engines; F5 is never imported at startup (T4 guard) and only really loaded in T9 by the controller. Real F5-API correctness is validated live in T9 (mirrors how Kokoro was validated), with an explicit "fix if signature differs" step.
- **No placeholders:** every code/test step is complete and runnable.
- **Out of scope (per spec):** fine-tuning, multi-clip voices, emotion sliders, in-place clip editing, denoising, multi-voice dialogue.
```
