# Changelog

All notable changes to Text2Audio are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
