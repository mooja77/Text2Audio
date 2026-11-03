# Licences used by Text2Audio

**Verified live on 2026-11-03.** Every licence below was read from the upstream LICENSE file, model card or PyPI metadata at the pinned commit or revision shown. Text2Audio itself is MIT. It does not bundle any model weights: the user's own install downloads them from Hugging Face at runtime.

This is a factual summary, not legal advice.

Verdicts are for Text2Audio's use: a free MIT app, models downloaded at runtime, possible future commercial use by JMS Dev Lab, and users who may sell the audiobooks they make.

- **ALLOWED**: permissive for this use, including commercial output.
- **ALLOWED-WITH-CONDITIONS**: fine if the stated condition is met.
- **BLOCKED**: not acceptable as currently shipped. The fix is stated.
- **UNRESOLVED**: no authoritative text was found.

## Summary

| Component | Used for | Licence | Verdict | Pinned source |
|---|---|---|---|---|
| F5-TTS code (`f5-tts` 1.1.22) | Voice cloning engine (optional `clone` extra) | MIT | ALLOWED | [LICENSE @45868ab](https://github.com/SWivid/F5-TTS/blob/45868abaabd74aabf03cd673d6dd00cc9d9c01ae/LICENSE) |
| F5-TTS weights `F5TTS_v1_Base` | Voice cloning (default checkpoint) | CC-BY-NC-4.0 | **BLOCKED** as shipped. Becomes ALLOWED-WITH-CONDITIONS once gated (see below) | [card @84e5a41](https://huggingface.co/SWivid/F5-TTS/blob/84e5a410d9cead4de2f847e7c9369a6440bdfaca/README.md) |
| Emilia dataset (F5 training data) | Not used directly | Emilia CC-BY-NC-4.0; Emilia-YODAS CC-BY-4.0 | n/a (it is the reason the F5 weights are NC) | [HF dataset @d7f2f73](https://huggingface.co/datasets/amphion/Emilia-Dataset/tree/d7f2f7340a6385696f3766c8049fa920a4707c07) (gated) |
| Vocos weights `charactr/vocos-mel-24khz` | F5-TTS vocoder | MIT | ALLOWED | [card @0feb3fd](https://huggingface.co/charactr/vocos-mel-24khz/blob/0feb3fdd929bcd6649e0e7c5a688cf7dd012ef21/README.md) |
| Vocos code (`vocos` 0.1.0) | F5-TTS vocoder | MIT | ALLOWED | [LICENSE @eb39abf](https://github.com/gemelo-ai/vocos/blob/eb39abfc42c1dee4854d9b10d44dd7d4fd3b0e53/LICENSE) |
| Kokoro-82M weights and voices | Default narration | Apache-2.0 | ALLOWED | [card @f3ff357](https://huggingface.co/hexgrad/Kokoro-82M/blob/f3ff3571791e39611d31c381e3a41a3af07b4987/README.md) |
| `kokoro` 0.9.4 (code) | Default narration | Apache-2.0 | ALLOWED | [LICENSE @dfb907a](https://github.com/hexgrad/kokoro/blob/dfb907a02bba8152ca444717ca5d78747ccb4bec/LICENSE) |
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
| numpy 2.5.4 | Arrays | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | ALLOWED | PyPI JSON |
| python-multipart 0.0.33 | Uploads | Apache-2.0 | ALLOWED | PyPI JSON |
| aiofiles 25.1.0 | File I/O | Apache-2.0 | ALLOWED | PyPI JSON |
| num2words 0.5.14 | Number normalising | LGPL | ALLOWED-WITH-CONDITIONS | PyPI JSON |
| pypdf 6.21.4 | PDF import | BSD-3-Clause | ALLOWED | PyPI JSON |
| gradio 6.31.0 (optional `classic`) | Classic UI | Apache-2.0 | ALLOWED | PyPI JSON |
| torch 2.15.0 | Inference | Apache-2.0 AND BSD and others (permissive) | ALLOWED | PyPI JSON |
| torchaudio 2.11.1 | F5 audio | BSD (classifier) | ALLOWED | PyPI JSON |
| spacy 3.8.18 / spacy-curated-transformers 2.1.2 | misaki[en] | MIT / MIT | ALLOWED | PyPI JSON |
| transformers 5.22.1 | kokoro dep | Apache 2.0 | ALLOWED | PyPI JSON |

PyPI versions are the latest on PyPI on 2026-11-03 (`https://pypi.org/pypi/<name>/json`). Raw PyPI output was captured with the release evidence.

---

## 1. F5-TTS code

- Pinned: `SWivid/F5-TTS` commit `45868abaabd74aabf03cd673d6dd00cc9d9c01ae`. `pyproject.toml` there says `version = "1.1.22"`. The latest on PyPI is also `f5-tts` 1.1.22, with classifier `License :: OSI Approved :: MIT License`.
- Quote (LICENSE): "MIT License / Copyright (c) 2024 Yushen CHEN / Permission is hereby granted, free of charge, to any person obtaining a copy of this software..."
- Quote (README, License section): "Our code is released under MIT License. The pre-trained models are licensed under the CC-BY-NC license due to the training data Emilia, which is an in-the-wild dataset."
- **Verdict: ALLOWED.** Keep the MIT notice.

## 2. F5-TTS weights (`F5TTS_v1_Base`)

- Pinned: HF `SWivid/F5-TTS` sha `84e5a410d9cead4de2f847e7c9369a6440bdfaca`. The repo has no separate LICENSE file; the only licence text is the card's `license:` field.
- Card front matter: `license: cc-by-nc-4.0` ... `datasets: - amphion/Emilia-Dataset`.
- Default checkpoint, from `src/f5_tts/api.py` @45868ab: `model="F5TTS_v1_Base"` and `repo_name, ckpt_step, ckpt_type = "F5-TTS", 1250000, "safetensors"`. So it downloads `hf://SWivid/F5-TTS/F5TTS_v1_Base/model_1250000.safetensors`.
- Upstream says the NC licence comes from the training data: "The pre-trained models are licensed under the CC-BY-NC license due to the training data Emilia".
- **Verdict: BLOCKED as currently shipped.** Text2Audio's Voices page shows a "Clone a voice" panel with no licence notice. A grep of `web/index.html` and `web/js/voices.js` for "commercial" or "licen" finds nothing. The only notices are in README.md and THIRD_PARTY_LICENSES.md, so a user can make a cloned-voice audiobook and sell it without ever being told about the restriction.
- **Gate that makes it ALLOWED-WITH-CONDITIONS:** (a) keep F5 opt-in. It already is: INSTALL.md has the user run `pip install f5-tts` themselves. (b) Show a clear notice in the clone panel and on any render that uses a cloned voice: "Cloned voices use F5-TTS weights licensed CC-BY-NC-4.0. Non-commercial use only." (c) Require one acknowledgement checkbox before the first clone. (d) Write a "non-commercial (F5-TTS CC-BY-NC-4.0)" note into the exported file's metadata or the book's details. (e) JMS Dev Lab must never use cloned output commercially, and must never make cloning a default. CC-BY-NC also requires attribution, so give credit to SWivid/F5-TTS with a link to the licence.

## 3. Emilia dataset

- Pinned: HF `amphion/Emilia-Dataset` sha `d7f2f7340a6385696f3766c8049fa920a4707c07`. The dataset is gated (`gated: auto`) and its README cannot be fetched without logging in. The terms were read from the public API `cardData` (`https://huggingface.co/api/datasets/amphion/Emilia-Dataset`).
- Card `license: cc-by-4.0`. The gate terms say: "1. The researcher shall use the Emilia dataset under the CC-BY-NC license and the Emilia-YODAS dataset under the CC-BY license."
- Amphion GitHub (`open-mmlab/Amphion` @26f6883, `preprocessors/Emilia/README.md`): "Emilia-Large combines the original 101k-hour Emilia dataset (licensed under `CC BY-NC 4.0`) with the brand-new 114k-hour **Emilia-YODAS dataset** (licensed under `CC BY 4.0`)". It also says: "Users are permitted to use this dataset only for non-commercial purposes under the CC BY-NC-4.0 license."
- **Do trained weights inherit the restriction?** The Emilia terms we could read say nothing about models trained on the data. The inheritance comes from F5's own statement, which licenses its weights CC-BY-NC "due to the training data Emilia". Treat F5 weights as NC either way. A model trained only on Emilia-YODAS (CC-BY) would not carry the NC term, but we found no verified permissive F5 checkpoint.

## 4. Vocos

- Weights: HF `charactr/vocos-mel-24khz` sha `0feb3fdd929bcd6649e0e7c5a688cf7dd012ef21`. Card front matter `license: mit`; the card text says "The code in this repository is released under the MIT license."
- Code: `gemelo-ai/vocos` @`eb39abfc42c1dee4854d9b10d44dd7d4fd3b0e53`, "MIT License / Copyright (c) 2023 Charactr Inc."
- **Verdict: ALLOWED.** Keep the MIT notice.

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

## 8. Python dependencies (PyPI JSON, 2026-11-03)

- fastapi 0.162.0: `license_expression: MIT`. ALLOWED.
- uvicorn 0.54.0: `BSD-3-Clause`. ALLOWED.
- soundfile 0.14.0: "BSD 3-Clause License". Its README says libsndfile "is a free, cross-platform, open-source (LGPL) library" and that the Windows wheels ship "own copy of libsndfile in the wheel". ALLOWED-WITH-CONDITIONS: libsndfile is loaded dynamically, which is LGPL-compliant. If Text2Audio ever bundles it, include the LGPL text and keep it replaceable.
- numpy 2.5.4: `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`. ALLOWED.
- python-multipart 0.0.33: `Apache-2.0`. ALLOWED.
- aiofiles 25.1.0: `Apache-2.0`. ALLOWED.
- num2words 0.5.14: "LGPL" (classifier "GNU Library or Lesser General Public License (LGPL)"). ALLOWED-WITH-CONDITIONS: use it unmodified as an imported library. If it is ever bundled, include the LGPL text.
- pypdf 6.21.4: `BSD-3-Clause`. ALLOWED.
- gradio 6.31.0: `Apache-2.0`. ALLOWED.
- torch 2.15.0: `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND ISC AND MIT AND Zlib`. ALLOWED.
- torchaudio 2.11.1: classifier "BSD License". ALLOWED.
- spacy 3.8.18: MIT. spacy-curated-transformers 2.1.2: MIT. en_core_web_sm: MIT (HF card). ALLOWED.
- transformers 5.22.1: "Apache 2.0 License". ALLOWED.
- phonemizer-fork 3.3.2: GPLv3+ (see section 6).

## 9. ffmpeg

- FFmpeg LICENSE.md @b21727a: "Most files in FFmpeg are under the GNU Lesser General Public License version 2.1 or later (LGPL v2.1+)... Some optional parts of FFmpeg are licensed under the GNU General Public License version 2 or later (GPL v2+)."
- gyan.dev (used by Text2Audio's installer via winget `Gyan.FFmpeg`): "All builds are 64-bit, static and licensed as GPLv3".
- BtbN/FFmpeg-Builds README @5ece628: "`gpl` Includes all dependencies, even those that require full GPL instead of just LGPL. `lgpl` Lacking libraries that are GPL-only." It also offers `nonfree` builds (fdk-aac), which must never be redistributed.
- **Verdict: ALLOWED-WITH-CONDITIONS.** Text2Audio runs ffmpeg as a separate process and installs it from winget, so it redistributes nothing. Encoded audio output is not covered by the GPL. **Condition:** never bundle a gyan.dev or BtbN `gpl` build without the GPL text and source offer. If a binary has to ship, use a BtbN `lgpl` or `lgpl-shared` build with the LGPL notice, and never a `nonfree` build.

---

## What this means for Text2Audio

1. **Kokoro narration, the default, is clean.** Apache-2.0 weights, voices and code. People can sell audiobooks made with it. Keep the Apache credit.
2. **Voice cloning (F5-TTS) is non-commercial.** The weights are CC-BY-NC-4.0. The app currently says so only in the README, not where people clone. Add an in-app notice and a one-time acknowledgement, tag cloned exports as non-commercial, and keep it opt-in. JMS Dev Lab must not use cloned output commercially.
3. **GPL parts are fine while the user's own machine installs them.** That covers espeak-ng, the espeak-ng DLL inside `espeakng-loader`, `phonemizer-fork`, and the gyan.dev ffmpeg. They become a problem only if Text2Audio ships a bundled build. If it ever does, ship that bundle under GPL-3.0 terms with source.
4. **Piper is not the permissive alternative the PRD assumed.** Current Piper is GPL-3.0, and most English voices derive from the research-only Lessac data or are NC. Only `en_US-ljspeech` and `en_GB-cori` look usable, and those need an allow-list.

## Corrections to THIRD_PARTY_LICENSES.md

1. **"espeak-ng ... installed separately, not redistributed" is incomplete.** Kokoro's own dependency chain (`kokoro` → `misaki[en]` → `espeakng-loader` 0.2.4) pip-installs a bundled `espeak-ng.dll` (GPL-3.0) with no licence file in the wheel. It also pulls in `phonemizer-fork` (GPL-3.0-or-later), which the file does not mention.
2. **"ffmpeg (LGPL/GPL depending on build)" is vague.** The installer installs `Gyan.FFmpeg`, and gyan.dev states every one of its builds is GPLv3.
3. **The F5 weights note is accurate, but the notice is missing from the app.** "Outputs of the cloning feature are restricted to non-commercial use" appears only in docs; the clone UI says nothing.
4. **The "Python libraries" section implies everything is permissive.** `num2words` is LGPL, `phonemizer-fork` is GPL-3.0+, and soundfile bundles LGPL libsndfile. The F5 dependency `vocos` has no licence in its PyPI metadata; its repo LICENSE is MIT.
5. **No upstream attribution is listed.** That is required by Apache-2.0 (Kokoro, misaki), CC-BY-NC-4.0 (F5 weights) and MIT (F5 code, Vocos). Add a short credits block with links to the licences.
6. **Kokoro, F5 code MIT, F5 weights CC-BY-NC-4.0, and Vocos MIT were all confirmed correct.**
7. **PRD claim to correct:** "Piper is a permissive alternative" is wrong. See section 7.

Evidence: raw licence texts and model cards were captured at the pinned revisions above on 2026-11-03 (kept in the maintainer's release evidence, not in this repository).
