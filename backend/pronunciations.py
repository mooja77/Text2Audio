"""Persistent global custom pronunciation rules (word -> say-as)."""
import json
import os
import threading


class PronunciationStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()

    def get_all(self) -> dict:
        if not os.path.isfile(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                value = json.load(f)
            if not isinstance(value, dict):
                return {}
            return {str(k).lower(): str(v) for k, v in value.items()
                    if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip()}
        except (json.JSONDecodeError, OSError):
            # Self-heal: this is on the render hot path. A corrupt/unreadable
            # file should not 500 every render or block rule editing.
            return {}

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def set_rule(self, word: str, say_as: str) -> None:
        with self._lock:
            data = self.get_all()
            data[word.lower()] = say_as
            self._save(data)

    def remove(self, word: str) -> None:
        with self._lock:
            data = self.get_all()
            if data.pop(word.lower(), None) is not None:
                self._save(data)
