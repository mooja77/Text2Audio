"""One-time server-side acknowledgement before cloning a voice.

Since 1.5.0 cloning uses Chatterbox (MIT code and weights), so cloned audiobooks may
be sold like any other. The gate now asks the one thing that still matters: that the
user has the right to clone the voice (their own, with the speaker's permission, or a
public-domain recording). 1.4 stored an F5-TTS (CC-BY-NC-4.0) licence acknowledgement
without a ``kind``; that answered a different question, so it does not count here.
"""
import datetime
import json
import os

KIND = "voice-rights-v1"
LICENSE = "MIT"
ATTRIBUTION = "ResembleAI/chatterbox"


def read_consent(path: str) -> dict:
    """Never raises: a missing, corrupt or older-kind file means not acknowledged."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
        if (isinstance(value, dict) and value.get("acknowledged") is True
                and value.get("kind") == KIND):
            at = value.get("acknowledgedAt")
            return {"acknowledged": True, "kind": KIND,
                    "acknowledgedAt": at if isinstance(at, str) else None}
    except (json.JSONDecodeError, OSError):
        pass
    return {"acknowledged": False, "kind": KIND, "acknowledgedAt": None}


def write_consent(path: str, acknowledged: bool) -> dict:
    data = {"acknowledged": bool(acknowledged), "kind": KIND,
            "acknowledgedAt": datetime.datetime.now().isoformat(timespec="seconds")
            if acknowledged else None}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return data
