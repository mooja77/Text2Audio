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

## Run

```powershell
python app.py
```

Your browser opens the app. Upload a `.txt` book, pick a voice, optionally set
title/author/cover, click **Detect chapters** to confirm the split, then
**Generate Audiobook**. The finished `.m4b` lands in `output/`.

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
