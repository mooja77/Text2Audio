# Third-Party Licenses

Text2Audio's own code is MIT-licensed (see `LICENSE`). It relies on third-party
models and libraries with their own licenses. The models are **downloaded at
runtime** from Hugging Face — they are not bundled in this repository. You are
responsible for complying with each model's license for your use case.

## Text-to-speech models

| Component | Used for | License | Notes |
|---|---|---|---|
| **Kokoro-82M** (`hexgrad/Kokoro-82M`) | Default narration (preset voices) | **Apache-2.0** | Permissive; commercial use OK. |
| **F5-TTS** (`SWivid/F5-TTS`) — code | Voice cloning engine | **MIT** | Permissive. |
| **F5-TTS** — model weights (`F5TTS_v1_Base`) | Voice cloning | **CC-BY-NC-4.0** | **Non-commercial.** Outputs of the cloning feature are restricted to non-commercial use unless you supply differently-licensed weights. |
| **Vocos** (`charactr/vocos-mel-24khz`) | F5-TTS vocoder | MIT | |

> **Commercial use of voice cloning:** the default F5-TTS weights are CC-BY-NC
> (non-commercial). For commercial cloning you would need permissively-licensed
> weights (e.g. an Apache-2.0 retrain) — none is wired in by default.

## System dependencies (installed separately, not redistributed)

- **ffmpeg** / **ffprobe** — audio encoding & analysis (LGPL/GPL depending on build).
- **espeak-ng** — phonemizer backend for Kokoro (GPL-3.0).

## Python libraries

Installed via `requirements.txt` under their own licenses, e.g. `fastapi`,
`uvicorn`, `soundfile`, `numpy`, `num2words`, `kokoro`, `f5-tts`, `torch`,
`torchaudio`, `gradio`. See each project for its license.

## Responsible voice cloning

Only clone voices you have the right to use — your own voice, voices you have
explicit permission to clone, or public-domain recordings. Do not impersonate
people or create misleading audio. See the "Responsible use" section of the
README.
