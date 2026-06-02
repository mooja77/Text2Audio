"""Persistent store of user-cloned voices (reference clip + metadata)."""
import datetime
import json
import os
import shutil
import subprocess
import uuid

SAMPLE_NAME = "sample.wav"
META_NAME = "meta.json"


def new_voice_id() -> str:
    return "v" + uuid.uuid4().hex[:9]


class VoiceStore:
    def __init__(self, base_dir: str):
        self.base = base_dir
        os.makedirs(self.base, exist_ok=True)

    def _dir(self, id: str) -> str:
        return os.path.join(self.base, id)

    def ref_path(self, id: str) -> str:
        return os.path.join(self._dir(id), SAMPLE_NAME)

    def get(self, id: str) -> dict | None:
        p = os.path.join(self._dir(id), META_NAME)
        if not os.path.isfile(p):
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def list(self) -> list[dict]:
        items = []
        if os.path.isdir(self.base):
            for name in os.listdir(self.base):
                m = self.get(name)
                if m:
                    items.append(m)
        items.sort(key=lambda m: m.get("created", ""), reverse=True)
        return items

    def delete(self, id: str) -> None:
        shutil.rmtree(self._dir(id), ignore_errors=True)

    def create(self, name: str, audio_bytes: bytes, src_ext: str, ref_text: str = "") -> dict:
        vid = new_voice_id()
        d = self._dir(vid)
        os.makedirs(d, exist_ok=True)
        src = os.path.join(d, "_src" + (src_ext if src_ext.startswith(".") else ".bin"))
        with open(src, "wb") as f:
            f.write(audio_bytes)
        out = self.ref_path(vid)
        try:
            subprocess.run(["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", "24000", out],
                           check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            shutil.rmtree(d, ignore_errors=True)
            raise ValueError("could not read that audio file") from exc
        finally:
            if os.path.exists(src):
                os.remove(src)
        manifest = {"id": vid, "name": name, "refText": ref_text or "",
                    "created": datetime.datetime.now().isoformat(timespec="seconds")}
        with open(os.path.join(d, META_NAME), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        return manifest
