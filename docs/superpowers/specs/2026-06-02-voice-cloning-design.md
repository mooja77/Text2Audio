# Voice Cloning (F5-TTS) — Design (Phase 3)

**Date:** 2026-06-02
**Status:** Approved design, ready for implementation planning
**Part of:** "Top-class output" effort. Phase 3 of 3 (Phases 1 audio-mastering & 2 text-normalization ✅, both merged to master).

## Goal

Let the user narrate audiobooks in a **cloned voice**: upload a short reference clip,
save it as a named voice, and use it like any built-in narrator. Powered by a local
**F5-TTS** engine, opt-in per render. Kokoro stays the fast default and is unchanged.

## Decisions (from brainstorming + research)

| Topic | Decision |
|---|---|
| Engine | **F5-TTS** (`f5-tts`): best long-text stability (non-autoregressive, no end-of-sentence hallucination), cleanest Windows install, low VRAM (~2–3 GB), personal-use license |
| Default vs opt-in | Kokoro stays default; cloned voices are selectable per render/preview |
| Voice management | **Saved library** — upload a clip, name it, reuse it; cloned voices appear alongside presets |
| Speed tradeoff | Quality over speed accepted (F5 ≈ 4–5× real-time on the 3090, much slower than Kokoro); a one-paragraph preview lets the user audition first |
| Reference transcript | Optional field; blank → F5 auto-transcribes (slower). Recommended to provide. |
| F5 dependency | Heavy + **optional**: never imported at startup; install `f5-tts` only to use cloning |
| Sample rate | F5 output resampled to 24 kHz (`SAMPLE_RATE`) to match Kokoro/M4B |

## Architecture

A pluggable engine layer behind the existing synth interface. The render pipeline,
mastering, normalization, and library are unchanged; only synthesizer construction
and voice resolution change.

```
voice id ──► resolve_synth(voice_id, speed)
                 ├─ preset id  → Synthesizer (Kokoro)        [pipeline/synth.py]
                 └─ cloned id  → ClonedSynthesizer (F5-TTS)  [pipeline/clone_synth.py]
                        both implement BaseSynthesizer.synth_paragraphs(...)
```

## Components

### `pipeline/synth.py` — refactor to a base class
- Add `class BaseSynthesizer`: implements `synth_chunks`, `synth_paragraphs`, and
  `preview` in terms of an abstract `synth_chunk(text) -> np.ndarray` (plus the existing
  module constants `SAMPLE_RATE`, `SENTENCE_GAP`, `PARAGRAPH_GAP`, `concat_with_gaps`).
- `Synthesizer` (Kokoro) becomes `class Synthesizer(BaseSynthesizer)` providing
  `__init__` (lazy kokoro import) and `synth_chunk`. Public API identical → existing
  `tests/test_synth.py` stays green.

### `pipeline/clone_synth.py` — F5-TTS engine (new)
- `class ClonedSynthesizer(BaseSynthesizer)`: `__init__(ref_wav, ref_text="", speed=1.0)`.
- Lazy-imports `f5_tts`; loads the F5 model **once** via a module-level cached singleton
  (`_get_model()`), shared across voices (reference is per-call).
- `synth_chunk(text)`: `model.infer(ref_file=ref_wav, ref_text=ref_text, gen_text=text,
  speed=speed)` → numpy audio + sample rate; resample to `SAMPLE_RATE` if needed; return float32.
- Raises a clear `RuntimeError("install f5-tts to use cloned voices")` if the import fails.

### `backend/voices.py` — cloned-voice store (new)
- `class VoiceStore(base_dir)` (mirrors `Library`): voices under `<base>/<id>/` with
  `sample.wav` + `meta.json` (`id, name, refText, created`).
- `create(name, audio_bytes, src_ext, ref_text) -> dict`: write the upload to a temp file,
  convert via **ffmpeg → mono 24 kHz WAV** `sample.wav`, save meta, return it.
- `list() -> list[dict]`, `get(id) -> dict|None`, `ref_path(id) -> str`, `delete(id)`.
- `new_voice_id()` helper (hex, like `library.new_id`).

### `backend/render.py` — engine-agnostic factory
- `render_audiobook`/`_render_into` already take `synth_factory`. Change its contract to
  `synth_factory(voice_id, speed) -> BaseSynthesizer` (was `(voice=, lang_code=, speed=)`).
  The per-chapter loop is otherwise unchanged. `custom_rules`, mastering, kept-WAVs all stay.

### `server.py` — resolution, endpoints, wiring
- Globals: `voices = VoiceStore(...)` (path derived like `pron`).
- `resolve_synth(voice_id, speed)`: preset → `Synthesizer(voice=voice_id,
  lang_code=PRESET_VOICES[voice_id], speed=speed)`; cloned → `ClonedSynthesizer(
  voices.ref_path(id), meta["refText"], speed)`; unknown → raise (→ 400). A module-level
  `SYNTH_FACTORY = resolve_synth` so tests can monkeypatch.
- `GET /api/voices`: returns presets (`kind:"preset"`) + `voices.list()` (`kind:"cloned"`,
  with `name`) in one list.
- `POST /api/voices/clone` (multipart `name`, `audio` file, optional `refText`) → `voices.create(...)`;
  reject empty name / missing audio (400); ffmpeg decode failure (400).
- `DELETE /api/voices/{id}` → `voices.delete(id)` (404 if not a cloned voice).
- Render `target` and `/api/voice-preview` call `SYNTH_FACTORY(voice_id, speed)`; the
  unknown-voice guard checks both `PRESET_VOICES` and the voice store.

### `web/` — clone UI
- `web/js/voices.js`: add a **"Clone a voice"** panel (name input, audio drop, optional
  transcript textarea, Create button → `POST /api/voices/clone`). Render cloned voices as
  cards alongside presets with a "Cloned" badge + ✕ delete; ▶ sample + Use unchanged.
- `web/js/create.js`: the voice `<select>` lists cloned voices grouped under "Your voices".
- Both read the unified `/api/voices` payload (which now carries `kind`/`name`).

## Data flow

1. Clone: upload clip + name (+ optional transcript) → `POST /api/voices/clone` → ffmpeg
   converts to `voices/<id>/sample.wav` + meta. Voice appears in `/api/voices`.
2. Preview/Render with a cloned id → `resolve_synth` builds a `ClonedSynthesizer` →
   F5 model (cached) synthesizes each chunk from the reference → same normalize → chunk →
   paragraph-gap → mastered M4B path as Kokoro.

## Error handling

- F5 not installed → `ClonedSynthesizer` construction raises a clear message; the render
  job emits it as an `error` SSE event; preset renders unaffected. Startup never imports F5.
- Clone: empty name / no audio → 400; undecodable audio (ffmpeg fails) → 400 "couldn't read that audio".
- Render/preview with unknown or deleted voice id → 400 "unknown voice".
- Cloned voice missing `sample.wav` → clear error at construction, not a crash.

## Testing (GPU-free)

- `VoiceStore`: create with a tiny real wav (ffmpeg convert), list/get/ref_path/delete; reject preset-id delete.
- `resolve_synth`: returns a Kokoro-type for a preset id, a Cloned-type for a stored id (F5 mocked / not loaded).
- `BaseSynthesizer` refactor: existing `tests/test_synth.py` stays green; the Kokoro `Synthesizer` still synthesizes paragraphs with the right gaps.
- `api`: `/api/voices` includes cloned entries with `kind`; `POST /api/voices/clone` creates one; render + preview with a cloned id use the cloned engine (a fake `ClonedSynthesizer`); `DELETE` works; unknown voice → 400.
- `render`: with a fake cloned synth, a cloned voice id renders a valid book (manifest records the voice id).
- `ClonedSynthesizer` real-F5 smoke test: skipped unless `RUN_F5=1` (mirrors the `RUN_KOKORO` Kokoro smoke).

## New dependency

`f5-tts` (added to `requirements.txt`, documented as a **heavy optional** install for cloning).
The README gains a "Voice cloning" section (install `f5-tts`; how to add a voice).

## Out of scope (YAGNI / later)

- Fine-tuning / training custom models (zero-shot reference only).
- Multiple reference clips per voice, emotion/expressiveness sliders (F5 has none; a future
  engine could).
- Editing a saved voice's clip in place (delete + re-create instead).
- Auto-denoising reference clips (user supplies a clean clip; ffmpeg only reformats).
- Per-chapter voice switching / multi-voice dialogue.
