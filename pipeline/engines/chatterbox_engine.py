"""Chatterbox (Resemble AI) engine adapter. Imported only inside the engine worker.

Code: chatterbox-tts (MIT). Weights: ResembleAI/chatterbox, MIT, pinned to
CHATTERBOX_REVISION. Every waveform Chatterbox returns carries Resemble AI's
imperceptible Perth watermark (resemble-perth, MIT), which marks it as AI-generated.
"""
import os
from pathlib import Path

import numpy as np

from pipeline.engines import (CHATTERBOX_FILES, CHATTERBOX_REPO, CHATTERBOX_REVISION,
                              STUDIO_VOICES)


def _hf_hub_download():
    from huggingface_hub import hf_hub_download
    return hf_hub_download


def _chatterbox_tts():
    from chatterbox.tts import ChatterboxTTS
    return ChatterboxTTS


class ChatterboxEngine:
    """One loaded Chatterbox model serving the studio voice and cloned voices.

    Chatterbox keeps its speaker "conditionals" on the model. The built-in narrator
    is the conditionals shipped as conds.pt; a clone replaces them with ones computed
    from the reference clip. Those are cached per reference so a book's chunks pay
    the cost once, and the built-in ones are restored for the studio voice.
    """

    def __init__(self, model):
        self.model = model
        self._builtin = model.conds
        self._ref = None
        self._ref_conds = None

    def synth(self, text, voice=None, ref=None, ref_text=""):
        if ref:
            if ref != self._ref:
                self.model.prepare_conditionals(ref)
                self._ref, self._ref_conds = ref, self.model.conds
            self.model.conds = self._ref_conds
        else:
            if voice and voice not in STUDIO_VOICES:
                raise ValueError(f"unknown studio voice: {voice}")
            self.model.conds = self._builtin
        wav = self.model.generate(text)
        try:
            wav = wav.detach().float().cpu().numpy()
        except AttributeError:
            pass
        return np.asarray(wav, dtype=np.float32).reshape(-1), int(self.model.sr)


def _pinned_dir():
    """Pinned snapshot dir written by backend.model_download, if every file has its exact size."""
    from backend import model_download as md
    root = md.chatterbox_dir()
    try:
        for s in md.MANIFEST[CHATTERBOX_REPO][1]:
            if os.path.getsize(os.path.join(root, *s.rel.split('/'))) != s.size:
                return None
    except OSError:
        return None
    return root


def load(device: str) -> ChatterboxEngine:
    pinned = _pinned_dir()
    if pinned:  # same cache as the installer: local path, no Hub lookup
        return ChatterboxEngine(_chatterbox_tts().from_local(Path(pinned), device))
    download = _hf_hub_download()
    path = None
    for name in CHATTERBOX_FILES:
        path = download(repo_id=CHATTERBOX_REPO, filename=name, revision=CHATTERBOX_REVISION)
    return ChatterboxEngine(_chatterbox_tts().from_local(Path(path).parent, device))
