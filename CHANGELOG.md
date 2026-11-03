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

### Changed (voice cloning licence)

- The clone panel now says, before anything else, that cloned voices can't be used
  in audiobooks you sell, and names the F5-TTS weights licence (CC-BY-NC-4.0,
  SWivid/F5-TTS) with links. A one-time acknowledgement is stored server-side in
  `data/clone-consent.json` (`GET`/`POST /api/clone-consent`).
  `POST /api/voices/clone` answers **HTTP 403** (`consent_required`) and creates
  nothing until it is acknowledged. Rendering or previewing with a stored clone
  (`/api/render`, `/api/render-upload`, `/api/voice-preview`) is refused the same
  way, so a voices folder restored from a backup cannot bypass the notice.
- A book rendered with a cloned voice records `license: "non-commercial (F5-TTS
  CC-BY-NC-4.0)"` and `licenseAttribution: "SWivid/F5-TTS"` in its `manifest.json`,
  and the Library shows a "do not sell" note on that book.

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
