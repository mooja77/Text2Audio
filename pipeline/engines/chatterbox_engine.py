"""Chatterbox (Resemble AI) engine adapter. Imported only inside the engine worker.

Code: chatterbox-tts (MIT). Weights: ResembleAI/chatterbox, MIT, pinned to
CHATTERBOX_REVISION. Every waveform Chatterbox returns carries Resemble AI's
imperceptible Perth watermark (resemble-perth, MIT), which marks it as AI-generated.
"""
import os
from pathlib import Path

import numpy as np

from pipeline.engines import CHATTERBOX_FILES, CHATTERBOX_REPO, STUDIO_VOICES


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


def load(device: str) -> ChatterboxEngine:
    """Verify the pinned files (exact size + streamed digest), then load from that directory.

    No Hub lookup ever happens here; missing or damaged files raise
    md.ModelUnavailable with install/repair guidance before the model is built."""
    from backend import model_download as md
    pinned = md.require_files(CHATTERBOX_REPO, list(CHATTERBOX_FILES))
    return ChatterboxEngine(_chatterbox_tts().from_local(Path(pinned), device))
