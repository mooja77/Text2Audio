# Third-Party Licenses

Text2Audio's own code is MIT-licensed (see `LICENSE`). It relies on third-party
models and libraries with their own licenses. The models are **downloaded at
runtime** from Hugging Face — they are not bundled in this repository. You are
responsible for complying with each model's license for your use case.

Every entry below was verified live against the upstream licence file or model
card at a pinned revision on 2026-11-03. The full record, with quotes, pinned
links and verdicts, is in [`docs/LICENSES.md`](docs/LICENSES.md).

## Text-to-speech models

| Component | Used for | License | Notes |
|---|---|---|---|
| **Kokoro-82M** (`hexgrad/Kokoro-82M`) weights and voices | Default narration (preset voices) | **Apache-2.0** | Permissive; commercial use OK. |
| **kokoro**, **misaki** (Python packages) | Default narration, text-to-phoneme | Apache-2.0 | |
| **F5-TTS** (`SWivid/F5-TTS`) — code | Voice cloning engine (optional) | **MIT** | Permissive. |
| **F5-TTS** — model weights (`F5TTS_v1_Base`) | Voice cloning (optional) | **CC-BY-NC-4.0** | **Non-commercial.** Upstream: "The pre-trained models are licensed under the CC-BY-NC license due to the training data Emilia". Audio made with a cloned voice must not be used commercially. |
| **Vocos** (`charactr/vocos-mel-24khz`, `gemelo-ai/vocos`) | F5-TTS vocoder | MIT | |

> **Commercial use of voice cloning:** the default F5-TTS weights are CC-BY-NC
> (non-commercial). For commercial cloning you would need permissively-licensed
> weights — none is wired in by default. Narration with the built-in Kokoro
> voices has no such restriction.

## Copyleft components installed on your machine (not redistributed by Text2Audio)

These are GPL or LGPL. Text2Audio does not ship them; your own installer, pip
or winget fetches them. That is fine for personal and commercial use of the
audio you make. Anyone who **bundles** them into a redistributed build (for
example a frozen .exe or zipped environment) must follow their licence terms,
including the GPL text and source.

- **espeak-ng** — phonemizer backend for Kokoro (GPL-3.0-or-later). The Windows
  installer installs it with winget. Kokoro's dependency chain
  (`kokoro` → `misaki[en]` → `espeakng-loader`) also pip-installs a bundled
  `espeak-ng.dll` (GPL-3.0).
- **phonemizer-fork** — espeak-ng wrapper pulled in by `misaki[en]` (GPL-3.0-or-later).
- **ffmpeg / ffprobe** — audio encoding and analysis. The installer uses the
  gyan.dev build via winget, which is GPLv3. Text2Audio runs it as a separate
  program; your audio output is not covered by the GPL.
- **libsndfile** (bundled inside the `soundfile` wheel, LGPL) and **num2words** (LGPL),
  both used as unmodified libraries.

## Python libraries (permissive)

`fastapi` (MIT), `uvicorn` (BSD-3-Clause), `soundfile` (BSD-3-Clause), `numpy`
(BSD-3-Clause and others), `python-multipart` (Apache-2.0), `aiofiles`
(Apache-2.0), `pypdf` (BSD-3-Clause), `spacy` and `en_core_web_sm` (MIT),
`transformers` (Apache-2.0), `torch` and `torchaudio` (BSD/Apache), and the
optional `gradio` (Apache-2.0).

## Credits

- Kokoro-82M by hexgrad — <https://huggingface.co/hexgrad/Kokoro-82M> — Apache License 2.0.
- misaki by hexgrad — <https://github.com/hexgrad/misaki> — Apache License 2.0.
- F5-TTS by Yushen Chen et al. (SWivid) — code MIT <https://github.com/SWivid/F5-TTS>;
  weights CC BY-NC 4.0 <https://creativecommons.org/licenses/by-nc/4.0/>.
- Vocos by Charactr Inc. — <https://github.com/gemelo-ai/vocos> — MIT.
- eSpeak NG — <https://github.com/espeak-ng/espeak-ng> — GPL-3.0-or-later.

## Responsible voice cloning

Only clone voices you have the right to use — your own voice, voices you have
explicit permission to clone, or public-domain recordings. Do not impersonate
people or create misleading audio. See the "Responsible use" section of the
README.
