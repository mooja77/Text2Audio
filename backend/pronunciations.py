"""Persistent global custom pronunciation rules (word -> say-as)."""
import json
import os


class PronunciationStore:
    def __init__(self, path: str):
        self.path = path

    def get_all(self) -> dict:
        if not os.path.isfile(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def set_rule(self, word: str, say_as: str) -> None:
        data = self.get_all()
        data[word.lower()] = say_as
        self._save(data)

    def remove(self, word: str) -> None:
        data = self.get_all()
        if data.pop(word.lower(), None) is not None:
            self._save(data)
