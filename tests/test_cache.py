import numpy as np

from backend.cache import ChunkCache
from pipeline.synth import SAMPLE_RATE


def test_chunk_cache_round_trip(tmp_path):
    cache = ChunkCache(str(tmp_path), max_bytes=1_000_000)
    key = {"voice": "a", "text": "hello", "speed": 1.0}
    assert cache.get(key) is None
    audio = np.linspace(-0.1, 0.1, 1000, dtype=np.float32)
    cache.put(key, audio)
    restored = cache.get(key)
    assert restored is not None and len(restored) == len(audio)


def test_chunk_cache_key_changes_with_text(tmp_path):
    cache = ChunkCache(str(tmp_path))
    cache.put({"text": "one"}, np.zeros(100, dtype=np.float32))
    assert cache.get({"text": "two"}) is None
