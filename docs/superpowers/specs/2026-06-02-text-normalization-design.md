# Text Normalization & Pronunciation — Design (Phase 2)

**Date:** 2026-06-02
**Status:** Approved design, ready for implementation planning
**Part of:** "Top-class output" effort. Phase 2 of 3 (Phase 1 = audio mastering ✅; Phase 3 = high-quality voice cloning, its own spec).

## Goal

Make the narrator read text correctly: expand numbers and abbreviations, and fix
mispronounced proper nouns (Irish names/places), via a built-in normalizer plus a
user-editable global pronunciation dictionary with a small UI.

## Context

- Render path: `backend/render.py:57` does `synth.synth_paragraphs(chunk_paragraphs(ch.text))`.
  Normalization slots in as `chunk_paragraphs(normalize_text(ch.text, rules))`.
- `pipeline/` holds parse/chunk/synth/assemble/ingest. `server.py` is the FastAPI app
  (top-tab UI: Library · Create · Voices). `backend/library.py` is the persistence pattern
  to mirror.

## Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Control | Built-in normalization **+** editable custom dictionary with a UI |
| Rule scope | **Global** (one dictionary for all renders) |
| Auto-detect | Out of scope (not chosen) |
| Numbers | Conservative: years (1500–2099), integers, ordinals; leave times/currency/decimals |
| Number lib | `num2words` (new dependency) |
| Abbreviations | Unambiguous only (Mr, Mrs, Dr, Capt, Lt, &, …); skip ambiguous (St) |
| Pronunciations | Built-in starter list (Cork names) merged with custom rules; whole-word, case-insensitive |
| UI | New top-nav tab **"Pronounce"** |
| Always on | Normalization runs on every render (no toggle); conservative by design |

## Components

### `pipeline/normalize.py`
Built-in constants:
- `ABBREVIATIONS: dict[str, str]` — e.g. `{"mr": "Mister", "mrs": "Missus", "dr": "Doctor", "capt": "Captain", "lt": "Lieutenant", "col": "Colonel", "sgt": "Sergeant", "&": "and"}`.
- `BUILTIN_PRONUNCIATIONS: dict[str, str]` — curated Cork-book names/places respelled phonetically (e.g. `{"carrigaline": "Carrigaleen", "owenabue": "Owen-a-boo", "shanbally": "Shan-bally", "danaher": "Danaher", "hanratty": "Hanratty", "zubieta": "Soo-bee-eta", "hegarty": "Hegarty", ...}`). Values are starting guesses the user can override.

Functions:
- `expand_numbers(text: str) -> str` — regex-find number tokens; 4-digit 1500–2099 → `num2words(n, to="year")`; ordinals like `3rd/21st` → `num2words(n, to="ordinal")`; bare integers → `num2words(n)`. Inserts the word form in place. Skips tokens with `$`, `:`, `%`, or a decimal point.
- `expand_abbreviations(text: str) -> str` — whole-word, case-insensitive replace using `ABBREVIATIONS` (handles a trailing period: `Mr.`/`Mr`).
- `apply_pronunciations(text: str, rules: dict) -> str` — whole-word, case-insensitive replace using `rules` (already-merged dict). Word boundaries so substrings are never touched.
- `normalize_text(text: str, custom_rules: dict | None = None) -> str` — runs expand_numbers → expand_abbreviations → apply_pronunciations, where the pronunciation dict is `{**BUILTIN_PRONUNCIATIONS, **(custom_rules or {})}` (custom overrides built-in). Keys are matched lowercased.

### `backend/pronunciations.py`
- `class PronunciationStore(path: str)`: `get_all() -> dict` (custom rules only; `{}` if file missing), `set_rule(word: str, say_as: str) -> None` (lowercases the key, persists JSON), `remove(word: str) -> None` (idempotent). JSON file at `path` (default `data/pronunciations.json`).

### `server.py`
- Module global `pron = PronunciationStore(os.environ.get("T2A_PRON_PATH", "data/pronunciations.json"))`.
- `GET /api/pronunciations` → `{"builtin": BUILTIN_PRONUNCIATIONS, "custom": pron.get_all()}`.
- `PUT /api/pronunciations/{word}` body `{sayAs: str}` → `pron.set_rule(word, sayAs)`; returns `{"custom": pron.get_all()}`. Reject empty `sayAs` with 400.
- `DELETE /api/pronunciations/{word}` → `pron.remove(word)`; returns `{"custom": pron.get_all()}`.
- Render path loads `pron.get_all()` and threads it into the render so chapters are normalized (see render change).

### `backend/render.py`
- Add `custom_rules: dict | None = None` to `render_audiobook`/`_render_into` (keyword, default None).
- In `_render_into`, change the per-chapter line to:
  `audio = synth.synth_paragraphs(chunk_paragraphs(normalize_text(ch.text, custom_rules)))`.
- `server.py`'s render `target` passes `custom_rules=pron.get_all()`.
- `remaster` does NOT re-normalize (it rebuilds from already-synthesized WAVs) — normalization only affects new renders, by design.

### `web/` — Pronounce tab
- `index.html`: add a `Pronounce` tab button + `tab-pronounce` pane; load a new `js/pronounce.js`.
- `js/app.js`: route the `pronounce` tab to `Pronounce.render()`.
- `js/pronounce.js`: fetch `/api/pronunciations`; render a table — an "Add rule" row (word, say-as, Add), the editable **custom** rules (with Remove), and the **built-in** rules shown read-only/greyed for reference. A small **Test** field: type any text and see how it will be transformed, by calling `POST /api/normalize-preview {text}` → `{normalized}` (text-only, instant). Audio auditioning of voices stays in the Voices tab.

### `server.py` (Test support)
- `POST /api/normalize-preview` body `{text: str}` → `{"normalized": normalize_text(text, pron.get_all())}`. Text-only, instant, no GPU.

## Data flow

1. User adds rules in the Pronounce tab → `PUT/DELETE /api/pronunciations` → `data/pronunciations.json`.
2. On render, `server` loads `pron.get_all()` → `render_audiobook(..., custom_rules=...)` → each chapter is `normalize_text`-ed before chunk/synth.
3. Normalize-preview lets the user see transformations live without rendering.

## Error handling

- `PUT` with empty/whitespace `sayAs` → 400.
- Missing dictionary file → `get_all()` returns `{}` (no crash); `set_rule` creates the file/dir.
- `num2words` on an out-of-range/edge token → guarded by the regex (only matches plain integers/ordinals); any unexpected `ValueError` leaves the original token unchanged.
- Word keys are lowercased on store and on match, so casing is consistent.

## Testing (GPU-free)

- `normalize`: years (`1801`→`eighteen oh one`), integers (`42`→`forty-two`), ordinals (`3rd`→`third`), skip `$5`/`3:30`/`3.5`; abbreviations (`Mr`/`Mr.`→`Mister`, case-insensitive); pronunciation whole-word replace (doesn't touch `Carrigaline` inside another word; case-insensitive); custom overrides built-in; `&`→`and`.
- `pronunciations` store: set/get/remove round-trip on a tmp file; lowercase keying; missing file → `{}`.
- `api`: GET returns builtin+custom; PUT adds (and 400 on empty); DELETE removes; normalize-preview returns transformed text.
- `render`: with a spy/fake synth that records the chunks it received, a custom rule (e.g. `{"foo": "bar"}`) makes `bar` appear and `foo` absent in what the synth got.

## New dependency

`num2words` (added to `requirements.txt`; pure-Python, small).

## Out of scope (YAGNI / later)

- Per-book rule sets (global only).
- Auto-detection / suggestion of mispronounced words.
- Audio "test" of a word (the Test field is text-only normalization preview; audio auditioning stays in Voices).
- Re-normalizing already-rendered books (normalization affects new renders only).
- IPA/phoneme input (rules are plain respellings).
