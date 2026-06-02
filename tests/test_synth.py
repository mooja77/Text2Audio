import os
import numpy as np
import pytest

from pipeline.synth import SAMPLE_RATE, PRESET_VOICES, concat_with_gaps


def test_sample_rate_is_24000():
    assert SAMPLE_RATE == 24000


def test_preset_voices_lang_codes_match_prefix():
    assert PRESET_VOICES["af_heart"] == "a"
    assert PRESET_VOICES["bf_emma"] == "b"
    # Every voice's lang_code equals the first letter of its id.
    assert all(lang == vid[0] for vid, lang in PRESET_VOICES.items())


def test_concat_with_gaps_empty():
    out = concat_with_gaps([])
    assert isinstance(out, np.ndarray)
    assert out.shape == (0,)


def test_concat_with_gaps_inserts_silence_between():
    a = np.ones(100, dtype=np.float32)
    b = np.ones(200, dtype=np.float32)
    gap_samples = int(0.5 * SAMPLE_RATE)
    out = concat_with_gaps([a, b], gap_seconds=0.5)
    assert out.shape[0] == 100 + gap_samples + 200
    # The gap region between the two clips is silent.
    assert np.all(out[100:100 + gap_samples] == 0.0)


def test_concat_with_gaps_single_array_no_gap():
    a = np.ones(50, dtype=np.float32)
    assert concat_with_gaps([a], gap_seconds=0.5).shape[0] == 50


@pytest.mark.skipif(os.environ.get("RUN_KOKORO") != "1",
                    reason="Set RUN_KOKORO=1 to run the GPU model smoke test")
def test_synthesizer_smoke():
    from pipeline.synth import Synthesizer
    synth = Synthesizer(voice="af_heart", lang_code="a")
    audio = synth.synth_chunk("Hello, this is a test.")
    assert isinstance(audio, np.ndarray)
    assert audio.shape[0] > SAMPLE_RATE // 4  # at least ~0.25s of audio


from pipeline.synth import SENTENCE_GAP, PARAGRAPH_GAP


def test_gap_constants():
    assert SENTENCE_GAP == 0.15 and PARAGRAPH_GAP == 0.6


def test_synth_paragraphs_uses_variable_gaps(monkeypatch):
    from pipeline.synth import Synthesizer

    # Build a Synthesizer without importing kokoro: bypass __init__.
    synth = Synthesizer.__new__(Synthesizer)
    synth.voice, synth.speed = "x", 1.0
    # one fixed 1000-sample clip per chunk
    monkeypatch.setattr(synth, "synth_chunk", lambda text: np.ones(1000, dtype=np.float32))

    # two paragraphs, one chunk each -> clipA + PARAGRAPH_GAP + clipB
    out = synth.synth_paragraphs([["a"], ["b"]])
    expected = 1000 + int(PARAGRAPH_GAP * SAMPLE_RATE) + 1000
    assert out.shape[0] == expected

    # one paragraph, two chunks -> clip + SENTENCE_GAP + clip
    out2 = synth.synth_paragraphs([["a", "b"]])
    expected2 = 1000 + int(SENTENCE_GAP * SAMPLE_RATE) + 1000
    assert out2.shape[0] == expected2
