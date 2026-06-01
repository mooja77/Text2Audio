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
