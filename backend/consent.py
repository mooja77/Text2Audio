"""One-time server-side acknowledgement of the F5-TTS (CC-BY-NC-4.0) clone licence."""
import datetime
import json
import os

LICENSE = "CC-BY-NC-4.0"
ATTRIBUTION = "SWivid/F5-TTS"
MANIFEST_LICENSE = "non-commercial (F5-TTS CC-BY-NC-4.0)"


def read_consent(path: str) -> dict:
    """Never raises: a missing or corrupt file means not acknowledged."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
        if isinstance(value, dict) and value.get("acknowledged") is True:
            at = value.get("acknowledgedAt")
            return {"acknowledged": True, "acknowledgedAt": at if isinstance(at, str) else None}
    except (json.JSONDecodeError, OSError):
        pass
    return {"acknowledged": False, "acknowledgedAt": None}


def write_consent(path: str, acknowledged: bool) -> dict:
    data = {"acknowledged": bool(acknowledged),
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
