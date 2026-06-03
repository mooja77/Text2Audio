# Contributing to Text2Audio

Thanks for your interest! Text2Audio is a free, local, open-source audiobook
generator. Contributions — bug reports, fixes, features, docs — are welcome.

## Getting set up

See the README's **Setup** section. In short:

```bash
python -m venv .venv
# activate it, then:
pip install --index-url https://download.pytorch.org/whl/cu124 torch
pip install -r requirements.txt
```

You also need **ffmpeg** and **espeak-ng** on your system (see the README).

## Running the tests

The suite is designed to run **without a GPU** — the TTS engines are mocked.

```bash
pytest -q
```

The GPU model tests are opt-in (and require the models installed):

```bash
# Kokoro:
RUN_KOKORO=1 pytest tests/test_synth.py
# F5-TTS voice cloning:
RUN_F5=1 pytest tests/test_clone_synth.py
```

Please keep the suite green and add tests for new behavior. The project follows
test-driven development — write the failing test first.

## Project layout

- `pipeline/` — text → audio pipeline (parse, ingest, normalize, chunk, synth, assemble).
- `backend/` — server support (library, jobs, render orchestration, voices, pronunciations).
- `server.py` — FastAPI app + REST/SSE API serving the web UI.
- `web/` — the vanilla-JS frontend (no build step).
- `app.py` — the original single-screen Gradio UI (still works).
- `tests/` — pytest suite.

## Guidelines

- Keep modules small and focused; match the existing style.
- Escape user-controlled text before inserting into the DOM (`T2A.esc`).
- Validate any client-supplied id before it touches the filesystem.
- For new TTS engines, implement `pipeline.synth.BaseSynthesizer` so the rest of
  the pipeline stays engine-agnostic. Heavy engines should be lazily imported and
  optional (and isolated in a subprocess if they conflict with others — see
  `pipeline/clone_synth.py`).

## License

By contributing, you agree your contributions are licensed under the MIT License.
