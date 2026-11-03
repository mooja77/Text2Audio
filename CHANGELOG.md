# Changelog

All notable changes to Text2Audio are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Studio accessibility pass (WCAG 2.2 AA): labels on every control, visible focus outlines, a skip link, `aria-live` announcements for render progress and an assertive alert region for errors, keyboard-operable dropzone, library cards and chapter rows, focus management in the beginner guide, and higher-contrast primary buttons. No change to the render flow.

- `backend/offline.py`: when the models are cached, `HF_HUB_OFFLINE`,
  `TRANSFORMERS_OFFLINE` and `HF_HUB_DISABLE_TELEMETRY` are set at the top of
  `server.py` and `pipeline/f5_worker.py`, before any Hugging Face import. A
  GPU-free test fails if a mocked render opens any socket. Measured with the
  Kokoro model cached and the network blocked: 218 s → 23 s per render start,
  3 → 0 connection attempts. A narrator voice not used before is still
  downloaded once on a connected PC, and a user's own `HF_HUB_OFFLINE` is left alone.

### Documentation

- `docs/LICENSES.md`: every model, dataset and library licence verified live at
  a pinned upstream revision (2026-11-03), with quotes and a verdict for each.
  Kokoro narration is Apache-2.0 and clean; the optional F5-TTS cloning weights
  are CC-BY-NC-4.0 (non-commercial). `THIRD_PARTY_LICENSES.md` corrected: the
  GPL `espeak-ng.dll` and `phonemizer-fork` that Kokoro's dependencies install,
  the GPLv3 ffmpeg build the installer uses, LGPL `num2words`/libsndfile, and a
  credits block.

### Changed (UX)

- First-run checklist (ffmpeg, espeak-ng, model download, free disk space) returned by `GET /api/health` as `checklist`/`ready` and shown at the top of Studio, with a next step for each failing item.
- Errors shown in the UI are plain language; raw stack text and JSON are never displayed. Render error events keep `message` and add `friendly`.

### Changed (API)

- **Unknown narrator voices now return HTTP 422 instead of HTTP 400** on
  `POST /api/render`, `POST /api/render-upload` and `POST /api/voice-preview`.
  The body is `{"detail": "unknown voice", "error": "unknown voice", "voice": "<id>"}`.
  `detail` keeps the shape used by the rest of the API, so callers that read it
  keep working; callers that test for `400` must accept `422`. The check runs
  before anything is written, so nothing is added to the library. (#15)
- Voice lookup (preset Kokoro voice or stored clone) now lives in one place,
  `backend/render.py::resolve_synthesizer`, which raises `UnknownVoiceError`
  rather than a raw `KeyError`. (#15)

## [1.3.0] - 2026-09-27

### Added

- A guided first-audiobook path in the web UI. (#10)

### Changed

- More reliable audiobook workflow: rendering, persistence and web workflow
  hardening. (#9, #11)

### Fixed

- Windows installer detects a real Python 3.10–3.12, stops clearly on failure
  and no longer recurses through winget. (#14, released after 1.3.0 on master)
