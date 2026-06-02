"""Kokoro-based synthesis and audio assembly helpers."""
import numpy as np

SAMPLE_RATE = 24000
SENTENCE_GAP = 0.15
PARAGRAPH_GAP = 0.6

# voice_id -> lang_code (lang_code must match the voice's language prefix).
PRESET_VOICES: dict[str, str] = {
    # American English — female
    "af_heart": "a", "af_bella": "a", "af_nicole": "a", "af_sarah": "a", "af_sky": "a",
    # American English — male
    "am_michael": "a", "am_adam": "a", "am_echo": "a", "am_liam": "a",
    # British English — female
    "bf_emma": "b", "bf_isabella": "b", "bf_alice": "b",
    # British English — male
    "bm_george": "b", "bm_lewis": "b", "bm_daniel": "b",
}


def concat_with_gaps(audio_arrays, gap_seconds: float = 0.3, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    arrays = [a for a in audio_arrays if a is not None and len(a) > 0]
    if not arrays:
        return np.zeros(0, dtype=np.float32)
    gap = np.zeros(int(gap_seconds * sample_rate), dtype=np.float32)
    out = []
    for i, a in enumerate(arrays):
        if i:
            out.append(gap)
        out.append(np.asarray(a, dtype=np.float32))
    return np.concatenate(out)


class Synthesizer:
    def __init__(self, voice: str = "af_heart", lang_code: str = "a",
                 device: str = "cuda", speed: float = 1.0):
        from kokoro import KPipeline
        self.pipeline = KPipeline(lang_code=lang_code, device=device)
        self.voice = voice
        self.speed = speed

    def synth_chunk(self, text: str) -> np.ndarray:
        parts = [audio for _, _, audio in self.pipeline(text, voice=self.voice, speed=self.speed)]
        return concat_with_gaps(parts, gap_seconds=0.0)

    def synth_chunks(self, chunks, progress=None) -> np.ndarray:
        out = []
        for i, chunk in enumerate(chunks):
            audio = None
            for _attempt in range(2):  # one retry
                try:
                    audio = self.synth_chunk(chunk)
                    break
                except Exception:
                    audio = None
            if audio is not None and len(audio) > 0:
                out.append(audio)
            if progress is not None:
                progress(i + 1, len(chunks))
        return concat_with_gaps(out, gap_seconds=0.3)

    def synth_paragraphs(self, paragraphs, progress=None) -> np.ndarray:
        total = sum(len(p) for p in paragraphs)
        done = 0
        para_audios = []
        for para in paragraphs:
            chunk_audios = []
            for chunk in para:
                audio = None
                for _attempt in range(2):  # one retry
                    try:
                        audio = self.synth_chunk(chunk)
                        break
                    except Exception:
                        audio = None
                if audio is not None and len(audio) > 0:
                    chunk_audios.append(audio)
                done += 1
                if progress is not None:
                    progress(done, total)
            joined = concat_with_gaps(chunk_audios, gap_seconds=SENTENCE_GAP)
            if len(joined) > 0:
                para_audios.append(joined)
        return concat_with_gaps(para_audios, gap_seconds=PARAGRAPH_GAP)

    def preview(self, text: str = "This is a sample of the selected narrator voice.") -> np.ndarray:
        return self.synth_chunk(text)
