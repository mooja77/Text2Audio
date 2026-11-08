# Changelog

All notable changes to Text2Audio are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Preserve recognised chapter headings when importing TXT, Markdown and text-based PDF books.
- Keep leading chapter numbers and years in detected titles and narration.
- List every supported manuscript format in the beginner guide.
- Clarify model preparation and the commercial-use label on older F5-TTS books in Help.

### Added

- I-1: NVIDIA and post-install CUDA/free-memory checks, with hardware results
  merged into existing settings.
- I-2: pinned Kokoro and optional Chatterbox model preparation with byte progress,
  disk-space checks, resumable partial downloads, digest repair and shared local
  cache paths. All English voices and the English language package are required
  for offline readiness.
- I-3: CPU/Kokoro fallback with persistent runtime state, explicit device override
  precedence, Studio/cloning refusal reasons and `device`/`engines` health fields.
  Late Studio memory failures stop the job with actionable guidance.
- I-4: packaged launcher checks, loopback port selection, plain startup/bind
  messages, persistent diagnostics and browser opening gated on this server's PID.
- I-5: Windows installer orchestration through Python support stages, including
  early persistent logging, pinned language-package repair and offline verification
  before success or Desktop shortcut creation.
- Integration tests for installer/runtime seams, with isolated server import and
  inherited-path regressions. Existing batch files are unchanged.

## [1.5.0] - 2026-11-04

New voice engine. The studio narrator and voice cloning now use Chatterbox
(Resemble AI; MIT code and weights), chosen by a measured bake-off of the
current open-source models. Cloned audiobooks may now be sold.

### Added

- **Studio Narrator** voice (Chatterbox's built-in voice), the default on PCs
  with an NVIDIA graphics card. Kokoro's 15 voices stay as the fast option and
  remain the default without one.
- `pipeline/engines/` and `pipeline/engine_worker.py`: an isolated worker
  process for neural engines, with Chatterbox's weights pinned to revision
  `5bb1f6e`.
- `GET /api/health` reports `studioVoices` and `defaultVoice`; `GET /api/voices`
  lists the studio voice first and gives every voice an `engine`.
- Manifests record which `engine` narrated the book.
- `docs/LICENSES.md` section 2: the November 2026 model shortlist, with each
  model's weights and code licence read at a pinned revision.

### Changed

- **Voice cloning uses Chatterbox instead of F5-TTS.** The clone panel now asks
  you once to confirm you have the right to clone the voice, instead of asking
  you to accept a non-commercial licence. The 1.4 acknowledgement no longer
  counts.
- Cloned voices accept a speed setting (ffmpeg `atempo`, pitch kept).
- `chatterbox-tts==0.1.7` is a core dependency (pins torch/torchaudio 2.6.0,
  transformers 5.2.0, numpy < 2). The Windows installer installs the CUDA 12.4
  build of torch 2.6.0 first.
- A failed chunk on the neural engine is retried once before the render stops.

### Removed

- F5-TTS and its Vocos vocoder (weights CC-BY-NC-4.0), `pipeline/f5_worker.py`,
  and the non-commercial mark on new books. Books cloned with F5 before 1.5.0
  keep their mark until you render them again.

### Fixed

- The chunk cache can no longer serve audio made by an older engine for the same
  cloned voice: neural cache keys now include the engine.

## [1.4.0] - 2026-11-03

Licence gating, a real offline guarantee, accessibility and plain-language help.
Every model and library licence was verified against its upstream source.

**Upgrade note (API):** an unknown narrator voice now returns HTTP 422 (was 400) on
render, render-upload and voice-preview; see "Changed (API)" below.

### Fixed

- Links in the clone licence notice and the Help licence table used the browser
  default colour (#0000ee, 1.84:1 on the dark panel). Links now use the theme
  accent (about 6:1). Measured with axe-core across all five tabs: 27 contrast
  violations → 0.

### Added

- `GET /api/licenses` lists the components in use with licence, verdict and source link, read from the `## Summary` table in `docs/LICENSES.md`. The Help tab renders it as a table. F5-TTS weights show as CC-BY-NC-4.0, Kokoro as Apache-2.0.

- Studio accessibility pass (WCAG 2.2 AA): labels on every control, visible focus outlines, a skip link, `aria-live` announcements for render progress and an assertive alert region for errors, keyboard-operable dropzone, library cards and chapter rows, focus management in the beginner guide, and higher-contrast primary buttons. No change to the render flow.

- `backend/offline.py`: when the models are cached, `HF_HUB_OFFLINE`,
  `TRANSFORMERS_OFFLINE` and `HF_HUB_DISABLE_TELEMETRY` are set at the top of
  `server.py` and `pipeline/f5_worker.py`, before any Hugging Face import. A
  GPU-free test fails if a mocked render opens any socket. Measured with the
  Kokoro model cached and the network blocked: 218 s → 23 s per render start,
  3 → 0 connection attempts. A narrator voice not used before is still
  downloaded once on a connected PC, and a user's own `HF_HUB_OFFLINE` is left alone. The F5 cloning worker is now
  spawned with the environment passed explicitly, and a test checks that it
  receives the offline flags and opens no sockets.

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

### Security

- The server only ever binds `127.0.0.1`. `server.main()` calls `assert_loopback()` and refuses to start on any other host; a test fails if `main()` would bind a non-loopback host. `GET /api/health` now includes `bind` (e.g. `127.0.0.1:8765`).

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
