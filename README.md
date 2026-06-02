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

## Run (Studio UI)

```powershell
.\.venv\Scripts\python.exe server.py
```

Opens the Text2Audio Studio in your browser. **Create** tab: drag in `.md`/`.txt`
chapter files (Markdown is auto-cleaned, one file per chapter), set
title/voice/speed, and Generate — live per-chapter progress streams as it
renders. **Voices** tab: audition any narrator. **Library** tab: every finished
audiobook with an in-app chapter player, retag, and delete. Finished books are
saved under `library/<id>/book.m4b`.

The classic single-screen Gradio UI is still available via `python app.py`
(upload one `.txt`, **Detect chapters**, **Generate Audiobook** → `output/`).

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
