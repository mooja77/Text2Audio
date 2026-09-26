"""Bounded persistent cache for synthesized narration chunks."""
import hashlib
import json
import os
import threading

import soundfile as sf

from pipeline.synth import SAMPLE_RATE


class ChunkCache:
    def __init__(self, base_dir: str, max_bytes: int = 5 * 1024**3):
        self.base = base_dir
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        os.makedirs(base_dir, exist_ok=True)

    def _path(self, key: dict) -> str:
        encoded = json.dumps(key, sort_keys=True, ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        return os.path.join(self.base, digest[:2], digest + ".wav")

    def get(self, key: dict):
        path = self._path(key)
        if not os.path.isfile(path):
            return None
        try:
            audio, rate = sf.read(path, dtype="float32")
            if rate != SAMPLE_RATE:
                return None
            os.utime(path, None)
            return audio
        except (OSError, RuntimeError):
            return None

    def put(self, key: dict, audio) -> None:
        path = self._path(key)
        with self._lock:
            if os.path.isfile(path):
                return
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temp = path + ".tmp.wav"
            sf.write(temp, audio, SAMPLE_RATE, subtype="PCM_16")
            os.replace(temp, path)
            self._prune()

    def _prune(self) -> None:
        files = []
        total = 0
        for root, _, names in os.walk(self.base):
            for name in names:
                if not name.endswith(".wav"):
                    continue
                path = os.path.join(root, name)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                total += stat.st_size
                files.append((stat.st_atime, stat.st_size, path))
        for _, size, path in sorted(files):
            if total <= self.max_bytes:
                break
            try:
                os.remove(path)
                total -= size
            except OSError:
                pass
