# Text2Audio 1.5.0

Text2Audio is a free audiobook studio that runs on your own computer. This
release changes the voices. The studio narrator and voice cloning now use
Chatterbox by Resemble AI, the best open-source model in a bake-off we ran on
3 and 4 November 2026. And cloned voices can now be used in audiobooks you sell.

## What's new

**A studio narrator voice.** On a PC with an NVIDIA graphics card, the default
narrator is now "Studio Narrator", Chatterbox's built-in voice. In our tests it
read the passage with the fewest mistakes of any built-in voice we tried, and
it kept the most consistent voice from sentence to sentence. It is slower than
the fast voices: see "How fast is it?" below.

**Cloning you can sell.** Cloning now uses Chatterbox too. Its code and weights
are MIT-licensed, so audiobooks made with a cloned voice can be sold. In our
tests it was the closest open-source match to a real speaker. You still need
the right to clone the voice: your own, one whose owner has given you
permission, or a public-domain recording. The app asks you to confirm that
once.

**The fast voices stay.** Kokoro's 15 British and American voices are still
there, and they are still the default on PCs without an NVIDIA graphics card.
They run much faster than real time even on a laptop CPU.

**Inaudible watermark.** Every studio or cloned recording carries Resemble AI's
Perth watermark. You can't hear it. It marks the audio as AI-generated and does
not limit what you can do with it.

**F5-TTS is gone.** 1.4 cloned voices with F5-TTS, whose weights are
non-commercial (CC-BY-NC-4.0). Books you made that way keep their "do not sell"
mark in the Library. Render them again in 1.5 to replace them with Chatterbox
audio. The app never reuses old F5 audio from its cache.

## How fast is it?

Measured on the test PC (RTX 3090, Windows 11) through the app itself, with the
models already downloaded and the internet blocked:

| Voice | Audio made | Time taken (including loading the model) |
|---|---|---|
| Studio Narrator (Chatterbox), two chapters | 108.6 s | 268.4 s |
| Cloned voice (Chatterbox), speed 1.1 | 27.8 s | 72.1 s |
| Heart (Kokoro) | 34.1 s | 20.2 s |

Timed sentence by sentence in the bake-off, Chatterbox took a median of 1.5
seconds per second of audio for the studio voice and 1.6 for a clone, so a
10-hour book takes roughly 15 hours. Kokoro took under 0.1 seconds. Chatterbox
needs about 4.5 GB of graphics memory and a one-off 3.2 GB download.

On a CPU without a graphics card, Chatterbox took about 5 seconds per second of
audio, which is too slow for books. Kokoro took 0.3 seconds per second of audio.

## How we chose

We listed the current open-weight text-to-speech models and kept only those
whose code **and** weights are under an open-source licence (MIT, Apache-2.0,
BSD or similar) that allows commercial use. That ruled out Fish Audio S2 Pro and
Drama-3, Voxtral, Breeze-TTS-2, Higgs TTS 3, OmniVoice and IndexTTS (non-commercial
or vendor licences), NVIDIA Magpie (NVIDIA's own licence), and Tencent AuK
(MIT, but it needs a non-commercial Qwen encoder to run). The full list, with
each licence read at a pinned revision, is in `docs/LICENSES.md`.

We then ran nine permitted models plus Kokoro on this PC. They all read the
same two-minute passage of Pride and Prejudice and the same paragraph of tricky
text (dates, money, abbreviations, place names), and cloned the same 6-second
public recording. Whisper large-v3 transcribed every result to count reading
errors. A speaker-recognition model (ECAPA) measured how close each clone was
to the real speaker, and UTMOS predicted naturalness.

| | Reading errors (WER) | Clone similarity to the real speaker | Tricky text when cloning |
|---|---|---|---|
| **Chatterbox** | 1.0% (built-in voice), 0.0% (clone) | **0.818** (best) | **19/20** (best) |
| Qwen3-TTS 1.7B | 0.0%, 0.0% | 0.817 | 17/20 |
| Chatterbox Multilingual V3 | 1.7%, 0.3% | 0.809 | 15/20 |
| VoxCPM2 | –, 2.0% | 0.803 | 17/20 |
| Kokoro (baseline) | 1.3% | (no cloning) | – |

For comparison, two real recordings of the same speaker scored 0.79 to 0.89.
Qwen3-TTS read as accurately and cloned almost as closely, but its built-in
English voice scored lowest for naturalness (UTMOS 3.93 against Chatterbox's
4.33 and Kokoro's 4.50), and it ran about two and a half to three times slower than Chatterbox.

## For developers

- New engine layer: `pipeline/engines/` (Chatterbox adapter, voice list, pinned
  weights revision) and `pipeline/engine_worker.py`, a generic JSON-over-stdio
  worker that replaces `pipeline/f5_worker.py`. `NeuralSynthesizer` and
  `ClonedSynthesizer` in `pipeline/clone_synth.py` talk to it. A per-chunk engine
  error is now retried once before the render stops, like Kokoro errors.
- Speed for neural voices is applied with ffmpeg's `atempo` (pitch kept).
- `GET /api/voices` puts `studio_narrator` (kind `studio`) first and adds an
  `engine` field. `GET /api/health` adds `studioVoices` and `defaultVoice`.
  `RenderRequest.voice` defaults to `defaultVoice`.
- Manifests record `engine` (`chatterbox` or `kokoro`). New books never get a
  `license` field.
- Chunk-cache keys for neural voices now include the engine (version 2). Kokoro
  keys are unchanged, so existing Kokoro caches still work.
- `/api/clone-consent` now records a voice-rights confirmation
  (`kind: voice-rights-v1`). A 1.4 F5 licence acknowledgement no longer counts.
- Dependencies: `chatterbox-tts==0.1.7` is now a core dependency. It pins
  `torch==2.6.0`, `torchaudio==2.6.0`, `transformers==5.2.0` and `numpy<2`. The
  Windows installer installs torch 2.6.0 from the CUDA 12.4 index first. The
  `clone` extra is now empty.
- Opt-in GPU test: `RUN_CHATTERBOX=1 pytest tests/test_clone_synth.py`.
