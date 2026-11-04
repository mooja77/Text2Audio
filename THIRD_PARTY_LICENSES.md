# Third-Party Licenses

Text2Audio's own code is MIT-licensed (see `LICENSE`). It relies on third-party
models and libraries with their own licenses. The models are **downloaded at
runtime** from Hugging Face — they are not bundled in this repository. You are
responsible for complying with each model's license for your use case.

Every entry below was verified live against the upstream licence file or model
card at a pinned revision on 2026-11-03 or 2026-11-04. The full record, with quotes, pinned
links and verdicts, is in [`docs/LICENSES.md`](docs/LICENSES.md).

## Text-to-speech models

| Component | Used for | License | Notes |
|---|---|---|---|
| **Chatterbox** (`ResembleAI/chatterbox`, pinned revision `5bb1f6e`) weights | Studio narrator voice and voice cloning (default) | **MIT** | Permissive; commercial use OK. |
| **chatterbox-tts** 0.1.7 (Python package) | Studio narrator voice and voice cloning | **MIT** | |
| **resemble-perth** 1.0.1 | Inaudible watermark on Chatterbox audio | MIT | Marks audio as AI-generated; does not restrict use. |
| **s3tokenizer** 0.3.0 | Chatterbox speech tokenizer | Apache-2.0 | |
| **Kokoro-82M** (`hexgrad/Kokoro-82M`) weights and voices | Fast narrator voices (any PC) | **Apache-2.0** | Permissive; commercial use OK. |
| **kokoro**, **misaki** (Python packages) | Fast narrator voices, text-to-phoneme | Apache-2.0 | |

> **Selling audiobooks:** both engines are open source and allow commercial use.
> Audiobooks made with the studio voice, a Kokoro voice, or a clone of a voice
> you have the right to use may be sold. The clone panel asks once that you
> confirm you have that right.
>
> **Removed in 1.5.0:** F5-TTS (weights CC-BY-NC-4.0) and its Vocos vocoder.
> Books cloned with F5 before 1.5.0 keep their "non-commercial (F5-TTS
> CC-BY-NC-4.0)" mark; re-render them to use Chatterbox.

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
- **pykakasi** — Japanese text library pulled in by `chatterbox-tts` for its
  multilingual model, which Text2Audio does not use (GPL-3.0-or-later).
- **ffmpeg / ffprobe** — audio encoding and analysis. The installer uses the
  gyan.dev build via winget, which is GPLv3. Text2Audio runs it as a separate
  program; your audio output is not covered by the GPL.
- **libsndfile** (bundled inside the `soundfile` wheel, LGPL) and **num2words** (LGPL),
  both used as unmodified libraries.

## Python libraries (permissive)

`fastapi` (MIT), `uvicorn` (BSD-3-Clause), `soundfile` (BSD-3-Clause), `numpy`
(BSD-3-Clause and others), `python-multipart` (Apache-2.0), `aiofiles`
(Apache-2.0), `pypdf` (BSD-3-Clause), `spacy` and `en_core_web_sm` (MIT),
`transformers` (Apache-2.0), `torch` and `torchaudio` (BSD/Apache), `gradio`
(Apache-2.0), and Chatterbox's `diffusers` (Apache-2.0), `safetensors` (Apache-2.0),
`conformer` (MIT), `librosa` (ISC), `pyloudnorm` (MIT), `omegaconf` (BSD) and
`spacy-pkuseg` (MIT).

## Credits

- Kokoro-82M by hexgrad — <https://huggingface.co/hexgrad/Kokoro-82M> — Apache License 2.0.
- misaki by hexgrad — <https://github.com/hexgrad/misaki> — Apache License 2.0.
- Chatterbox by Resemble AI — <https://github.com/resemble-ai/chatterbox> and
  <https://huggingface.co/ResembleAI/chatterbox> — MIT.
- Perth watermarker by Resemble AI — <https://github.com/resemble-ai/perth> — MIT.
- S3Tokenizer by Xingchen Song — <https://github.com/xingchensong/S3Tokenizer> — Apache License 2.0.
- eSpeak NG — <https://github.com/espeak-ng/espeak-ng> — GPL-3.0-or-later.

## Responsible voice cloning

Only clone voices you have the right to use — your own voice, voices you have
explicit permission to clone, or public-domain recordings. Do not impersonate
people or create misleading audio. See the "Responsible use" section of the
README.
