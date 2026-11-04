# Licences used by Text2Audio

**Verified live on 2026-11-03 and 2026-11-04.** Every licence below was read from the upstream LICENSE file, model card or PyPI metadata at the pinned commit or revision shown. Text2Audio itself is MIT. It does not bundle any model weights: the user's own install downloads them from Hugging Face at runtime.

This is a factual summary, not legal advice.

Verdicts are for Text2Audio's use: a free MIT app, models downloaded at runtime, possible future commercial use by JMS Dev Lab, and users who may sell the audiobooks they make.

- **ALLOWED**: permissive for this use, including commercial output.
- **ALLOWED-WITH-CONDITIONS**: fine if the stated condition is met.
- **BLOCKED**: not acceptable as currently shipped. The fix is stated.
- **UNRESOLVED**: no authoritative text was found.

Since 1.5.0 every model Text2Audio runs has open-source code and weights (MIT or Apache-2.0) that allow commercial use. Nothing in use is non-commercial.

## Summary

| Component | Used for | Licence | Verdict | Pinned source |
|---|---|---|---|---|
| Chatterbox weights `ResembleAI/chatterbox` (English: `t3_cfg`, `s3gen`, `ve`, `tokenizer`, `conds`) | Studio narrator voice and voice cloning (default) | MIT | ALLOWED | [card @5bb1f6e](https://huggingface.co/ResembleAI/chatterbox/blob/5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18/README.md) |
| Chatterbox code (`chatterbox-tts` 0.1.7) | Studio narrator voice and voice cloning (default) | MIT | ALLOWED | [LICENSE @5de7a54](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/LICENSE) |
| `resemble-perth` 1.0.1 (Perth watermarker) | Marks Chatterbox audio as AI-generated (inaudible) | MIT | ALLOWED | [LICENSE @ff1c8ac](https://github.com/resemble-ai/perth/blob/ff1c8ac55a97/LICENSE) |
| `s3tokenizer` 0.3.0 | Chatterbox speech tokenizer | Apache-2.0 | ALLOWED | [LICENSE @9bf5d84](https://github.com/xingchensong/S3Tokenizer/blob/9bf5d84/LICENSE) |
| `pykakasi` 2.3.0 (pulled in by `chatterbox-tts`) | Japanese text for Chatterbox's multilingual model (not used by Text2Audio's English path) | GPL-3.0-or-later | ALLOWED-WITH-CONDITIONS | [PyPI](https://pypi.org/project/pykakasi/2.3.0/) |
| Kokoro-82M weights and voices | Fast narrator voices (any PC) | Apache-2.0 | ALLOWED | [card @f3ff357](https://huggingface.co/hexgrad/Kokoro-82M/blob/f3ff3571791e39611d31c381e3a41a3af07b4987/README.md) |
| `kokoro` 0.9.4 (code) | Fast narrator voices | Apache-2.0 | ALLOWED | [LICENSE @dfb907a](https://github.com/hexgrad/kokoro/blob/dfb907a02bba8152ca444717ca5d78747ccb4bec/LICENSE) |
| `misaki` 0.9.4 (G2P) | Kokoro text-to-phoneme | Apache-2.0 | ALLOWED | [LICENSE @fba1236](https://github.com/hexgrad/misaki/blob/fba1236595f2d2bf21d414ba6e57d25256afada3/LICENSE) |
| `phonemizer-fork` 3.3.2 (pulled in by `misaki[en]`) | espeak-ng wrapper | GPL-3.0-or-later | ALLOWED-WITH-CONDITIONS | [PyPI](https://pypi.org/project/phonemizer-fork/3.3.2/) |
| espeak-ng | Kokoro phonemizer backend | GPL-3.0-or-later | ALLOWED-WITH-CONDITIONS | [COPYING @a6ad07d](https://github.com/espeak-ng/espeak-ng/blob/a6ad07d4d7b58194ae671809bf194bc0ce967af9/COPYING) |
| `espeakng-loader` 0.2.4 | Ships `espeak-ng.dll` for misaki | Loader code MIT; bundled DLL GPL-3.0 | ALLOWED-WITH-CONDITIONS | [LICENSE @0ddc87a](https://github.com/thewh1teagle/espeakng-loader/blob/0ddc87adf77e5850d7eeb542ac8a87d421b64daa/LICENSE) |
| spaCy `en_core_web_sm` (downloaded by misaki at runtime) | English G2P support | MIT | ALLOWED | [card @8fb6f81](https://huggingface.co/spacy/en_core_web_sm/blob/8fb6f8155286360bf5486fe399e2738d1df7ded2/README.md) |
| Piper code, old `rhasspy/piper` (archived) | Proposed alternative engine | MIT | ALLOWED, but archived and unmaintained | [LICENSE.md @73c04d8](https://github.com/rhasspy/piper/blob/73c04d81d5590ecc46e522de3601ce7fb29fc2be/LICENSE.md) |
| Piper code, current `OHF-Voice/piper1-gpl` (`piper-tts` 1.8.0) | Proposed alternative engine | GPL-3.0 | ALLOWED-WITH-CONDITIONS | [COPYING @1088097](https://github.com/OHF-Voice/piper1-gpl/blob/10880972db9e0aca101fed350eadf8f49deefe9f/COPYING) |
| Piper voices (`rhasspy/piper-voices`) | Proposed voices | Repo tag says MIT, but each voice has its own dataset licence | Per voice; see section 7 | [repo @e7229f7](https://huggingface.co/rhasspy/piper-voices/tree/e7229f7d33a10e145e109b886d661984201ac3c4) |
| ffmpeg / ffprobe (installer uses winget `Gyan.FFmpeg`) | Encoding and analysis | gyan.dev builds are GPLv3 | ALLOWED-WITH-CONDITIONS | [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/), [FFmpeg LICENSE.md @b21727a](https://github.com/FFmpeg/FFmpeg/blob/b21727ae6f097b9ca31cd0167e2d006dc9c09e63/LICENSE.md) |
| fastapi 0.162.0 | Web server | MIT | ALLOWED | PyPI JSON |
| uvicorn 0.54.0 | Web server | BSD-3-Clause | ALLOWED | PyPI JSON |
| soundfile 0.14.0 (+ bundled libsndfile) | Audio I/O | BSD-3-Clause; libsndfile LGPL | ALLOWED-WITH-CONDITIONS | [LICENSE @e829339](https://github.com/bastibe/python-soundfile/blob/e8293394e6b712240f06aea5d074956481abf33e/LICENSE) |
| numpy 1.26.4 (Chatterbox needs numpy < 2) | Arrays | BSD-3-Clause | ALLOWED | PyPI JSON |
| python-multipart 0.0.33 | Uploads | Apache-2.0 | ALLOWED | PyPI JSON |
| aiofiles 25.1.0 | File I/O | Apache-2.0 | ALLOWED | PyPI JSON |
| num2words 0.5.14 | Number normalising | LGPL | ALLOWED-WITH-CONDITIONS | PyPI JSON |
| pypdf 6.21.4 | PDF import | BSD-3-Clause | ALLOWED | PyPI JSON |
| gradio 6.8.0 (pinned by `chatterbox-tts`; also the optional `classic` UI) | Classic UI | Apache-2.0 | ALLOWED | PyPI JSON |
| torch 2.6.0 / torchaudio 2.6.0 (pinned by `chatterbox-tts`) | Inference | BSD-3-Clause / BSD | ALLOWED | PyPI JSON |
| transformers 5.2.0 (pinned by `chatterbox-tts`) | Chatterbox and Kokoro | Apache 2.0 | ALLOWED | PyPI JSON |
| diffusers 0.29.0 / safetensors 0.5.3 / conformer 0.3.2 | Chatterbox | Apache-2.0 / Apache-2.0 / MIT | ALLOWED | PyPI JSON |
| librosa 0.11.0 / pyloudnorm 0.2.0 / omegaconf 2.4.0 / spacy-pkuseg 1.0.2 | Chatterbox | ISC / MIT / BSD / MIT | ALLOWED | PyPI JSON |
| spacy 3.8.18 / spacy-curated-transformers 2.1.2 | misaki[en] | MIT / MIT | ALLOWED | PyPI JSON |

PyPI versions are the versions pinned by `requirements.txt` and `chatterbox-tts` 0.1.7, or the latest on PyPI on 2026-11-03 where nothing pins them (`https://pypi.org/pypi/<name>/<version>/json`).

---

## 1. Chatterbox (studio voice and voice cloning, default since 1.5.0)

- **Weights**: HF `ResembleAI/chatterbox` sha `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`. Card front matter: `license: mit`. The repo has no separate LICENSE file; the card describes the models as "Resemble AI's production-grade open source TTS models". Text2Audio downloads only the English model's files at that pinned revision: `ve.safetensors`, `t3_cfg.safetensors`, `s3gen.safetensors`, `tokenizer.json` and `conds.pt` (about 3.2 GB). `conds.pt` is the built-in narrator ("Studio Narrator" in the app).
- **Code**: `resemble-ai/chatterbox` commit `5de7a54aa4e5e2baadb0182dde554908b48b85c2`, LICENSE: "MIT License / Copyright (c) 2025 Resemble AI / Permission is hereby granted, free of charge, to any person obtaining a copy of this software...". PyPI `chatterbox-tts` 0.1.7 (uploaded 2026-03-26), licence field "MIT License / Copyright (c) 2025 Resemble AI".
- **Training data**: the card says only "Trained on 0.5M hours of cleaned data". No dataset is named, so we could not check it, as with Kokoro's synthetic sources. The weights' own licence is MIT.
- **Watermark**: the card says "Every audio file generated by Chatterbox includes Resemble AI's Perth (Perceptual Threshold) Watermarker - imperceptible neural watermarks that survive MP3 compression, audio editing, and common manipulations". The watermarker (`resemble-perth` 1.0.1, `resemble-ai/perth` @ff1c8ac) is MIT. It does not restrict use. It marks the audio as AI-generated, and the app says so in the clone panel and the docs.
- **Selling audiobooks**: MIT puts no limit on the use of output. People can sell audiobooks made with the studio voice or with a clone of a voice they have the right to use. The app asks once that users confirm they have that right (their own voice, the speaker's permission, or a public-domain recording); see `backend/consent.py`.
- **Dependencies**: `s3tokenizer` 0.3.0 is Apache-2.0 (`xingchensong/S3Tokenizer` @9bf5d84). `pykakasi` 2.3.0 is GPL-3.0-or-later. It is a hard dependency of `chatterbox-tts` for the multilingual model, which Text2Audio does not use. As with espeak-ng, pip installs it on the user's machine and Text2Audio redistributes nothing, so the section 6 condition applies.
- **Verdict: ALLOWED.** Keep the MIT notices and credit Resemble AI.

## 2. November 2026 model shortlist

John's rule (2026-11-03): only models whose **code and weights** are under a real open-source licence (MIT, Apache-2.0, BSD or similar) that allows commercial use. Vendor "open model" licences, non-commercial licences and anything needing a paid licence are out. Each licence was read from the model card front matter (Hugging Face API `cardData`) and the code repo's LICENSE at the pinned revision. The cards were saved with the bake-off evidence.

| Model (released) | Weights licence @ revision | Code licence @ commit | Verdict | Bake-off on this PC |
|---|---|---|---|---|
| **Chatterbox** (English, 0.5B; Apr 2025, card updated Jun 2026) | MIT @5bb1f6e | MIT @5de7a54 | **PERMITTED. Chosen** | Yes (winner) |
| Chatterbox Multilingual V3 (0.5B; 2026) | MIT @5bb1f6e (same repo) | MIT @5de7a54 | PERMITTED | Yes |
| Chatterbox-Turbo (350M; Dec 2025) | MIT @749d1c1 | MIT @5de7a54 | PERMITTED | Yes |
| Chatterbox-Nano (110M; Apr 2026) | MIT @71ccd1d | MIT @5de7a54 | PERMITTED | Yes |
| Qwen3-TTS 12Hz 1.7B Base / CustomVoice (Jan 2026) | Apache-2.0 @fd4b254 / @0c0e305; tokenizer Apache-2.0 @7dd38ad | Apache-2.0 @022e286 (`QwenLM/Qwen3-TTS`) | PERMITTED | Yes |
| VoxCPM2 (2B; Apr 2026) | Apache-2.0 @32279ef ("free for commercial use") | Apache-2.0 @cce58a5 (`OpenBMB/VoxCPM`) | PERMITTED | Yes |
| Audio8-TTS-Realistic-Air (0.6B; Oct 2026) | Apache-2.0 @23c305c (LICENSE and NOTICE in repo) | Apache-2.0 @1d64afc (`Edge0-AI/Audio8_TTS`) | PERMITTED. Runs `trust_remote_code` | Yes |
| Ming-3.0-tts-0.5B (Sep 2026) | MIT @7247f4c | MIT @a39b806 (`inclusionAI/Ming-3.0-tts`) | PERMITTED | Yes |
| Kokoro-82M (baseline) | Apache-2.0 @f3ff357 | Apache-2.0 @dfb907a | PERMITTED | Yes (baseline) |
| Tencent AuK (1.5B; Aug 2026) | MIT @790742b ("refers solely to training code, inference code, parameters, and weights") | MIT @0d40366 | **BLOCKED**: it needs `Qwen/Qwen2.5-Omni-3B` as its text encoder (README: "The current implementation uses Qwen2.5-Omni-3B"), and that model is `qwen-research` @f75b40e: "FOR NON-COMMERCIAL PURPOSES ONLY" | No |
| NVIDIA Magpie TTS Multilingual 357M | `nvidia-open-model-license` @446bff5 | n/a | EXCLUDED: vendor licence, not open source (John's rule) | No |
| Fish Audio S2 Pro (Mar 2026), Fish Drama-3 (Oct 2026) | `fish-audio-research-license` @1de9996 / @78e5ab7 | n/a | EXCLUDED: research licence; commercial use needs a paid licence | No |
| Mistral Voxtral-4B-TTS-2603 | CC-BY-NC-4.0 @b81be46 | n/a | EXCLUDED: non-commercial | No |
| BreezeBlue Breeze-TTS-2 (Aug 2026) | `breezeblue-research-and-non-commercial-license` @3e28c51 | n/a | EXCLUDED: non-commercial | No |
| Boson Higgs TTS 3 4B (Jun 2026) | `boson-higgs-tts-3-research-and-non-commercial-license` @239f63f | n/a | EXCLUDED: non-commercial | No |
| k2-fsa OmniVoice (Mar 2026) | Card: "The pre-trained model is licensed under the CC-BY-NC due to constraints from its training data (e.g., Emilia)" @c5fdb5c | Apache-2.0 | EXCLUDED: non-commercial weights | No |
| IndexTTS-2.5 (Aug 2026) | `bilibili-model-license` @c39ce5b | n/a | EXCLUDED: vendor licence | No |
| Supertonic-3 (May 2026) | OpenRAIL @3cadd1e | n/a | EXCLUDED: use-restricted RAIL licence, not open source | No |
| Kitten TTS 2 (Sep 2026) | `stellon-labs-community-license` @c93cb7c | n/a | EXCLUDED: vendor licence | No |
| Audio8-TTS-Preview-0.1b (Aug 2026) | `audio8-community-license-v1.0` @8c83702 | n/a | EXCLUDED: vendor licence (the 0.6B models above are Apache-2.0) | No |
| Kyutai Pocket TTS / TTS 1.6B | CC-BY-4.0 @db04f0e / @f654396 | MIT/Apache | EXCLUDED: CC-BY-4.0 allows commercial use with attribution, but it is a content licence, not an MIT/Apache/BSD-style software licence (John's rule) | No |
| Microsoft VibeVoice-1.5B | MIT @c00898d | MIT @16fb2cb | PERMITTED by licence, not tested. The card says "We do not recommend using VibeVoice in commercial or real-world applications without further testing and development. This model is intended for research and development purposes only." | No |
| Fun-CosyVoice3-0.5B, MOSS-TTS, GLM-TTS, Maya-2-Native, OpenF5-TTS-Base, Phonon-31M-en, Inflect-Micro-v2 | Apache-2.0 @29e01c4, Apache-2.0 @b6b0229, MIT @b3feb69, Apache-2.0 @87a83ef, Apache-2.0 @28e45df, Apache-2.0 @92741c5, Apache-2.0 @9d86284 | Apache-2.0 / MIT | PERMITTED by licence, not tested (time; ranked below the tested models on their own published English results, or Indic-first, or tiny CPU models) | No |

The bake-off results and samples are in the maintainer's evidence folder and summarised in docs/RELEASE-NOTES-1.5.0.md.

## 3. Removed in 1.5.0: F5-TTS

1.4 cloned voices with F5-TTS. Its code is MIT (`SWivid/F5-TTS` @45868ab), but its weights (`F5TTS_v1_Base`, HF `SWivid/F5-TTS` @84e5a41) are CC-BY-NC-4.0 "due to the training data Emilia". The Vocos vocoder (`charactr/vocos-mel-24khz` @0feb3fd, MIT) was used only by F5. Chatterbox replaces both, with permissive weights and better measured cloning. Text2Audio 1.5 no longer installs or runs F5. Audiobooks made with a cloned voice before 1.5 keep their "non-commercial (F5-TTS CC-BY-NC-4.0)" mark in the library. Re-rendering them with 1.5 removes it, because the new audio no longer comes from F5.

## 4. Kokoro stays

Kokoro is kept as the light, fast engine for PCs without an NVIDIA graphics card. It is about 40 times faster than Chatterbox on the test PC, it runs faster than real time on a CPU, and its narration measured as well as Chatterbox's. See section 5 for its licence.

## 5. Kokoro-82M, `kokoro`, `misaki`

- Weights and voices: HF `hexgrad/Kokoro-82M` sha `f3ff3571791e39611d31c381e3a41a3af07b4987`. Card `license: apache-2.0`. Quote: "This is an Apache-licensed model, and Kokoro has been deployed in numerous projects and commercial APIs. We welcome the deployment of the model in real use cases."
- Training data, per the card: "Kokoro was trained exclusively on **permissive/non-copyrighted audio data** and IPA phoneme labels." Listed sources: "Public domain audio", "Audio licensed under Apache, MIT, etc" and "Synthetic audio generated by closed TTS models from large providers". The CC BY sources listed are Koniwa (CC BY 3.0) and SIWIS (CC BY 4.0). Note: whether those closed providers' terms allow their output to be used for training is not stated, and we did not verify it. The weights' own licence is Apache-2.0.
- `kokoro` 0.9.4: `hexgrad/kokoro` @`dfb907a02bba8152ca444717ca5d78747ccb4bec`, Apache License 2.0. It requires `misaki[en]>=0.9.4`.
- `misaki` 0.9.4: `hexgrad/misaki` @`fba1236595f2d2bf21d414ba6e57d25256afada3`, Apache License 2.0. Its `en` extra pulls in `phonemizer-fork`, `espeakng-loader`, `spacy`, `spacy-curated-transformers` and `num2words`. At runtime `misaki/en.py` calls `spacy.cli.download("en_core_web_sm")`. That model's card (@8fb6f81) says "**License** | `MIT`".
- **Verdict: ALLOWED** (Apache-2.0: keep the licence and NOTICE, and credit hexgrad/Kokoro-82M).

## 6. espeak-ng, `espeakng-loader`, `phonemizer-fork`

- espeak-ng @`a6ad07d4d7b58194ae671809bf194bc0ce967af9`: COPYING is "GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007". The README says "eSpeak NG Text-to-Speech is released under the GPL version 3 or later license."
- `espeakng-loader` 0.2.4: repo LICENSE @0ddc87a is "MIT License / Copyright (c) 2025 thewh1teagle". **The Windows wheel bundles the GPL binary.** We listed the contents of `espeakng_loader-0.2.4-py3-none-win_amd64.whl` without running it: `espeakng_loader/espeak-ng.dll` (419,328 bytes) plus `espeak-ng-data`, with **no LICENSE or COPYING file in the wheel**. PyPI metadata has an empty licence field.
- `phonemizer-fork` 3.3.2: PyPI classifier `GNU General Public License v3 or later (GPLv3+)`.
- **Verdict: ALLOWED-WITH-CONDITIONS.** Today Text2Audio redistributes none of these. The installer runs `winget install eSpeak-NG.eSpeak-NG`, and pip pulls in `espeakng-loader` and `phonemizer-fork` on the user's machine. That is fine. **Condition:** if Text2Audio ever ships a frozen or bundled build (PyInstaller, zipped venv, MSI) containing `espeak-ng.dll`, espeak-ng data or `phonemizer-fork`, that bundle must be distributed under GPL-3.0 terms, with the GPL text and the corresponding source (or a written offer). Text2Audio's MIT code is GPL-compatible, so this is possible, but it must be done deliberately.

## 7. Piper

- **Old code**, `rhasspy/piper` @`73c04d81d5590ecc46e522de3601ce7fb29fc2be`: "MIT License / Copyright (c) 2022 Michael Hansen". The repo is archived. Its README says: "Development has moved: https://github.com/OHF-Voice/piper1-gpl".
- **Current code**, `OHF-Voice/piper1-gpl` @`10880972db9e0aca101fed350eadf8f49deefe9f`: COPYING is GPL v3. The README says it is "A fast and local neural text-to-speech engine that embeds espeak-ng for phonemization." PyPI `piper-tts` 1.8.0 licence: `GPL-3.0-or-later`.
- **Voices**: HF `rhasspy/piper-voices` sha `e7229f7d33a10e145e109b886d661984201ac3c4`. The repo tag says `license: mit`, but every voice's MODEL_CARD names its own dataset licence:

| Voice (medium) | MODEL_CARD dataset licence (verbatim) | Training | Verdict |
|---|---|---|---|
| en_US-lessac | "License: https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html" | "Trained from scratch." | **BLOCKED** |
| en_US-libritts_r | "License: CC BY 4.0" | "Fine-tuned from English lessac medium" | **BLOCKED** (inherits lessac base) |
| en_GB-alan | "License: See URL" → mimic3-voices `apope_low/LICENSE`: "Copyright 2022 Mycroft AI / All Rights Reserved" | "Finetuned from U.S. English lessac voice" | **BLOCKED** |
| en_GB-jenny_dioco | "License: See URL" → Jenny dataset: "Commercial use is permitted." with attribution "the voice must be referred to as "Jenny"" | "Finetuned from U.S. English lessac voice" | **BLOCKED** (inherits lessac base) |
| en_US-ryan | "License: CC BY-NC-SA 4.0" | Finetuned from lessac | **BLOCKED** |
| en_US-amy | "License: See URL" (https://github.com/MycroftAI/mimic3-voices). No amy voice exists in that repo's `voices/en_US` today | Finetuned from lessac | **BLOCKED** (lessac base); dataset licence UNRESOLVED |
| en_US-hfc_female | "https://creativecommons.org/licenses/by-nc-sa/4.0/deed.en" | Finetuned from lessac | **BLOCKED** |
| en_US-ljspeech | "License: public domain" | "Trained from scratch for 1000 epochs ... using the LJ Speech dataset" | ALLOWED-WITH-CONDITIONS (see below) |
| en_GB-cori | "License: public domain" (LibriVox) | "Trained from scratch" | ALLOWED-WITH-CONDITIONS (see below) |

- Why lessac blocks the voices built on it: the Blizzard 2013 Lessac licence (fetched 2026-11-03) grants use "exclusively for Research Purposes only", and its definition "excludes ... using the Materials for any commercial purpose, including the development, marketing, commercialisation, sale or licencing of voice synthesis ... products or services". It adds: "the Audio Book Recordings are not licenced under this Agreement for use as audio books".
- **Verdict:** Piper is **not** a clean permissive alternative. The maintained code is GPL-3.0 and embeds espeak-ng. Most common English voices are lessac-based or NC. The only defensible candidates we found are `en_US-ljspeech` and `en_GB-cori`. They are public-domain data trained from scratch, but they are community uploads with no explicit weight licence beyond the repo's MIT tag. **Conditions:** use the archived MIT `rhasspy/piper` runtime, or accept GPL-3.0 for `piper-tts` (fine if not redistributed bundled; see section 6). Ship only an allow-list of those two voices, and record each voice's MODEL_CARD.

## 8. Python dependencies (PyPI JSON, 2026-11-03 and 2026-11-04)

- fastapi 0.162.0: `license_expression: MIT`. ALLOWED.
- uvicorn 0.54.0: `BSD-3-Clause`. ALLOWED.
- soundfile 0.14.0: "BSD 3-Clause License". Its README says libsndfile "is a free, cross-platform, open-source (LGPL) library" and that the Windows wheels ship "own copy of libsndfile in the wheel". ALLOWED-WITH-CONDITIONS: libsndfile is loaded dynamically, which is LGPL-compliant. If Text2Audio ever bundles it, include the LGPL text and keep it replaceable.
- numpy 1.26.4 (Chatterbox requires numpy < 2 on Python < 3.13): classifier "BSD License". ALLOWED.
- python-multipart 0.0.33: `Apache-2.0`. ALLOWED.
- aiofiles 25.1.0: `Apache-2.0`. ALLOWED.
- num2words 0.5.14: "LGPL" (classifier "GNU Library or Lesser General Public License (LGPL)"). ALLOWED-WITH-CONDITIONS: use it unmodified as an imported library. If it is ever bundled, include the LGPL text.
- pypdf 6.21.4: `BSD-3-Clause`. ALLOWED.
- gradio 6.8.0 (pinned by `chatterbox-tts`): `Apache-2.0`. ALLOWED.
- torch 2.6.0 (pinned by `chatterbox-tts`): `BSD-3-Clause`. torchaudio 2.6.0: classifier "BSD License". ALLOWED.
- spacy 3.8.18: MIT. spacy-curated-transformers 2.1.2: MIT. en_core_web_sm: MIT (HF card). ALLOWED.
- transformers 5.2.0 (pinned by `chatterbox-tts`): "Apache 2.0 License". ALLOWED.
- Chatterbox's other pins: diffusers 0.29.0 "Apache 2.0 License"; safetensors 0.5.3 "Apache Software License"; conformer 0.3.2 MIT; librosa 0.11.0 ISC; pyloudnorm 0.2.0 MIT; omegaconf 2.4.0 "BSD License"; spacy-pkuseg 1.0.2 MIT; s3tokenizer 0.3.0 "Apache2.0"; resemble-perth 1.0.1 "MIT License". ALLOWED.
- pykakasi 2.3.0: `GPL-3.0-or-later` (see sections 1 and 6).
- phonemizer-fork 3.3.2: GPLv3+ (see section 6).

## 9. ffmpeg

- FFmpeg LICENSE.md @b21727a: "Most files in FFmpeg are under the GNU Lesser General Public License version 2.1 or later (LGPL v2.1+)... Some optional parts of FFmpeg are licensed under the GNU General Public License version 2 or later (GPL v2+)."
- gyan.dev (used by Text2Audio's installer via winget `Gyan.FFmpeg`): "All builds are 64-bit, static and licensed as GPLv3".
- BtbN/FFmpeg-Builds README @5ece628: "`gpl` Includes all dependencies, even those that require full GPL instead of just LGPL. `lgpl` Lacking libraries that are GPL-only." It also offers `nonfree` builds (fdk-aac), which must never be redistributed.
- **Verdict: ALLOWED-WITH-CONDITIONS.** Text2Audio runs ffmpeg as a separate process and installs it from winget, so it redistributes nothing. Encoded audio output is not covered by the GPL. **Condition:** never bundle a gyan.dev or BtbN `gpl` build without the GPL text and source offer. If a binary has to ship, use a BtbN `lgpl` or `lgpl-shared` build with the LGPL notice, and never a `nonfree` build.

---


## What this means for Text2Audio

1. **Every model Text2Audio runs is open source and allows commercial use.** Chatterbox (MIT) narrates the studio voice and clones voices. Kokoro (Apache-2.0) is the fast engine. People can sell the audiobooks they make, including with a cloned voice they have the right to use. Keep the MIT and Apache credits.
2. **The cloning gate now asks about voice rights, not licences.** Users confirm once that they may clone the voices they upload. Older F5 books keep their non-commercial mark.
3. **Chatterbox audio carries an inaudible Perth watermark** that identifies it as AI-generated. This is disclosed in the app and the docs.
4. **GPL parts are fine while the user's own machine installs them.** That covers espeak-ng, the espeak-ng DLL inside `espeakng-loader`, `phonemizer-fork`, `pykakasi` and the gyan.dev ffmpeg. They become a problem only if Text2Audio ships a bundled build. If it ever does, ship that bundle under GPL-3.0 terms with source.
5. **Piper is not the permissive alternative the PRD assumed.** Current Piper is GPL-3.0, and most English voices derive from the research-only Lessac data or are NC. Only `en_US-ljspeech` and `en_GB-cori` look usable, and those need an allow-list.

Evidence: raw licence texts and model cards were captured at the pinned revisions above on 2026-11-03 and 2026-11-04 (kept in the maintainer's release evidence, not in this repository).
