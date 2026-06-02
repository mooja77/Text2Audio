"""F5-TTS voice-cloning synthesizer (heavy, optional, lazily imported)."""
import numpy as np

from pipeline.synth import BaseSynthesizer, SAMPLE_RATE

_MODEL = None


def _import_f5():
    from f5_tts.api import F5TTS
    return F5TTS


def _get_model():
    global _MODEL
    if _MODEL is None:
        try:
            F5TTS = _import_f5()
        except Exception as exc:  # not installed / import failure
            raise RuntimeError("install f5-tts to use cloned voices") from exc
        _MODEL = F5TTS()
    return _MODEL


def _resample(wav: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return np.asarray(wav, dtype=np.float32)
    n_out = int(round(len(wav) * sr_out / sr_in))
    x = np.linspace(0, len(wav), n_out, endpoint=False)
    return np.interp(x, np.arange(len(wav)), wav).astype(np.float32)


class ClonedSynthesizer(BaseSynthesizer):
    def __init__(self, ref_wav: str, ref_text: str = "", speed: float = 1.0):
        self.ref_wav = ref_wav
        self.ref_text = ref_text or ""
        self.speed = float(speed)
        self._model = _get_model()

    def synth_chunk(self, text: str) -> np.ndarray:
        wav, sr, _ = self._model.infer(
            ref_file=self.ref_wav, ref_text=self.ref_text,
            gen_text=text, speed=self.speed)
        return _resample(np.asarray(wav, dtype=np.float32), sr, SAMPLE_RATE)
