# Audio Mastering & Non-Destructive Renders — Design (Phase 1)

**Date:** 2026-06-02
**Status:** Approved design, ready for implementation planning
**Part of:** "Top-class output" effort. Phase 1 of 3 — Phase 2 = pronunciation/text normalization, Phase 3 = high-quality voice engine + cloning (each its own spec).

## Goal

Make Text2Audio's audio output sound *mastered and professional* without changing the
TTS model, and make renders *non-destructive* so any book can be re-mastered (loudness,
bitrate, pacing) in seconds without re-synthesizing.

## Context (current behavior)

- `pipeline/assemble.py` encodes the `.m4b` at **AAC 64k** with **no audio filtering**
  (`-c:a aac -b:a 64k`).
- `pipeline/synth.py` joins sentence chunks with a flat **0.3 s** gap; `pipeline/chunk.py`
  normalizes whitespace and discards paragraph boundaries.
- `backend/render.py` **deletes** each chapter WAV after building the `.m4b`, so re-mastering
  requires a full GPU re-render.
- Decisions from brainstorming carried forward: Phase 3 will keep Kokoro as the fast default
  and add an opt-in cloning engine behind the existing `synth.py` interface — so nothing here
  may hard-couple to Kokoro specifics.

## Decisions

| Topic | Decision |
|---|---|
| Bitrate | AAC **64k → 128k** (module constant `DEFAULT_BITRATE = "128k"`) |
| Mastering filters | `highpass=f=80, loudnorm=I=-19:TP=-2:LRA=11` (audiobook target ≈ −19 LUFS, −2 dBTP) |
| Mastering toggle | `build_m4b(..., master: bool = True, bitrate: str = DEFAULT_BITRATE)` |
| Pacing | Paragraph-aware: ~**0.15 s** between sentences, ~**0.6 s** at paragraph breaks |
| Renders | **Non-destructive** — keep per-chapter WAVs under `library/<id>/wav/` |
| Re-master | `remaster(library, id, ...)` + `POST /api/library/{id}/remaster` + UI button |
| Purge | `POST /api/library/{id}/purge-wav` + UI button to reclaim disk |
| WAV retention | `KEEP_WAVS` (default on); existing pre-Phase-1 renders (no WAVs) can't be re-mastered |

## Component changes

### `pipeline/assemble.py` — mastering in the encode
- Add `DEFAULT_BITRATE = "128k"` and the filter constant
  `MASTER_FILTERS = "highpass=f=80,loudnorm=I=-19:TP=-2:LRA=11"`.
- `build_m4b(chapter_wavs, output_path, book_title=None, author=None, cover=None,
  ffmpeg="ffmpeg", master: bool = True, bitrate: str = DEFAULT_BITRATE)`.
  - When `master` is True, add `["-af", MASTER_FILTERS]` to the ffmpeg command.
  - Replace the hardcoded `"64k"` with `bitrate`.
- Chapter timestamps are still computed from the source WAV durations (mastering filters do
  not change duration), so chapter markers stay correct.

### `pipeline/chunk.py` — paragraph-aware chunking (additive)
- Keep `chunk_text` unchanged (still used and tested).
- Add `chunk_paragraphs(text: str, max_chars: int = 400) -> list[list[str]]`: split on blank
  lines into paragraphs, then run each paragraph through the existing sentence-chunking logic,
  returning a list of paragraphs, each a list of sentence chunks. Empty paragraphs are dropped.

### `pipeline/synth.py` — variable gaps
- Add constants `SENTENCE_GAP = 0.15`, `PARAGRAPH_GAP = 0.6`.
- Add `Synthesizer.synth_paragraphs(paragraphs, progress=None) -> np.ndarray`: synthesize each
  sentence chunk, join chunks within a paragraph with `SENTENCE_GAP`, join paragraphs with
  `PARAGRAPH_GAP` (reusing `concat_with_gaps`). Retains the existing per-chunk retry/skip and
  the empty-result guard. `synth_chunks` stays for back-compat/tests.

### `backend/render.py` — non-destructive + paragraph pacing
- Use `chunk_paragraphs` + `synth_paragraphs` per chapter (replacing `chunk_text` +
  `synth_chunks`). Empty-chapter silence guard retained.
- Write chapter WAVs under `library/<id>/wav/chapter_NNN.wav` and **do not delete them** when
  `KEEP_WAVS` is true; record `wavFiles` (ordered list of `wav/...` relative paths) and
  `wavKept: true` in the manifest. Manifest also records `bitrate` and `mastered: true`.
- New `remaster(library, id, *, bitrate=DEFAULT_BITRATE, master=True) -> dict`: read the
  manifest, rebuild `book.m4b` from the kept WAVs (titles from `manifest["chapters"]`), update
  and save the manifest (`bitrate`, `mastered`). Raises if `wavKept` is false/absent.
- New `purge_wavs(library, id) -> dict`: delete `library/<id>/wav/`, set `wavKept: false`,
  clear `wavFiles`, save manifest.

### `server.py` — endpoints
- `POST /api/library/{id}/remaster` (body: optional `{bitrate, master}`) → updated manifest;
  404 if missing, 409/400 if no kept WAVs.
- `POST /api/library/{id}/purge-wav` → updated manifest.
- Both reuse the existing `_check_id` id-validation guard.

### `web/js/library.js` — UI
- In the detail/player view actions row, add **Re-master** (calls remaster, then reloads the
  detail) and **Purge source audio** (confirm → purge → reload). Show the disk note only when
  `wavKept` is true; hide Re-master when WAVs are absent (older renders).

## Data flow

1. Render: chapters → `chunk_paragraphs` → `synth_paragraphs` (variable gaps) → WAVs kept in
   `library/<id>/wav/` → `build_m4b(..., master=True, bitrate="128k")` → manifest records
   `wavFiles`, `wavKept`, `bitrate`, `mastered`.
2. Re-master: `POST /remaster` → rebuild `book.m4b` from kept WAVs with chosen settings →
   manifest updated. No GPU.
3. Purge: `POST /purge-wav` → `wav/` removed, manifest flags updated.

## Error handling

- `remaster` on an entry without kept WAVs → 400 with a clear message ("re-render required").
- Missing ffmpeg already handled by `build_m4b`'s shutil.which check.
- Purge is idempotent (ignore-missing); re-master after purge → the 400 path.

## Testing (GPU-free)

- `assemble`: `build_m4b(master=True)` includes `-af` with the master filter and `-b:a 128k`;
  produces a valid chaptered `.m4b` (ffprobe chapter count/titles); `master=False` omits `-af`.
- `chunk`: `chunk_paragraphs` groups sentences by paragraph, respects `max_chars`, drops empty
  paragraphs, never splits words.
- `synth`: `synth_paragraphs` with a fake synth returns audio whose length reflects
  SENTENCE_GAP vs PARAGRAPH_GAP (e.g. two paragraphs of one chunk each = chunkA + PARAGRAPH_GAP
  + chunkB).
- `render`: with a fake synth + real ffmpeg — WAVs are retained under `wav/`, manifest has
  `wavKept/wavFiles/bitrate/mastered`; `remaster` rebuilds the m4b and updates the manifest;
  `purge_wavs` removes the dir and flips the flags; `remaster` after purge raises.
- `api`: remaster endpoint returns updated manifest; purge endpoint flips flags; bad id → 404.

## Out of scope (later phases / YAGNI)

- Pronunciation/number normalization (Phase 2).
- New TTS engine / voice cloning (Phase 3).
- Per-chapter re-render, waveform display, configurable LUFS in the UI (a fixed audiobook
  target is used; the API accepts overrides for power use).
- Re-mastering the already-rendered Cork book / sample entries (their WAVs were deleted before
  this change) — those require a re-render.
