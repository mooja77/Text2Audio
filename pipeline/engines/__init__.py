"""Neural voice engines that run in the isolated worker (pipeline.engine_worker).

Chatterbox (Resemble AI, MIT code and weights) is the default engine for the studio
narrator voice and for cloned voices. It won the November 2026 bake-off on this
project's hardware: see docs/LICENSES.md for the licence record and the release
notes for the measured results. Kokoro stays in-process as the light, fast engine.

This module must stay import-light: the server imports it, but the engine itself is
only imported inside the worker process.
"""
DEFAULT_ENGINE = "chatterbox"

# engine name -> module defining load(device) -> engine with .synth(...)
ENGINE_MODULES = {"chatterbox": "pipeline.engines.chatterbox_engine"}

CHATTERBOX_REPO = "ResembleAI/chatterbox"
# Weights are pinned to the revision whose licence (MIT) was verified; see docs/LICENSES.md.
CHATTERBOX_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
CHATTERBOX_FILES = ("ve.safetensors", "t3_cfg.safetensors", "s3gen.safetensors",
                    "tokenizer.json", "conds.pt")

# Hugging Face repos each engine needs, for offline detection in the worker.
ENGINE_REPOS = {"chatterbox": (CHATTERBOX_REPO,)}

INSTALL_HINT = "install chatterbox-tts to use the studio voice and cloned voices"

# Built-in voices on the neural engine. Chatterbox ships one built-in narrator.
DEFAULT_STUDIO_VOICE = "studio_narrator"
STUDIO_VOICES = {
    DEFAULT_STUDIO_VOICE: {"engine": "chatterbox", "label": "Studio Narrator",
                           "accent": "Studio quality", "gender": "Male"},
}
