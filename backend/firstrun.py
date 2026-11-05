"""First-run checklist and plain-language error messages (no raw stack text)."""
import re
import shutil

MIN_FREE_BYTES = 2 * 1024**3
GENERIC_ERROR = ("Something went wrong. Please try again. If it keeps happening, "
                 "check the setup checklist at the top of the page.")

_FRIENDLY = [
    (r"no space left|disk full", "Your disk is full. Free up some space and try again."),
    (r"en_core_web_sm|language model|model files are missing",
     "A voice model or the English language package is missing or damaged. Double-click "
     "Install Text2Audio.bat to repair it. It is safe to run again."),
    (r"ffmpeg", "A required audio tool is missing. Check the setup checklist at the top of the page."),
    (r"chatterbox|voice engine worker",
     "The studio voice engine is not available. Choose a Kokoro narrator, or run "
     "Install Text2Audio.bat again to add it."),
    (r"timed out", "The voice engine took too long to respond. Try again, or try a shorter chapter."),
    (r"cancel", "The audiobook was cancelled."),
    (r"connection|urlopen|resolve|offline|max retries",
     "Text2Audio could not download the voice model. Connect to the internet for the first run and try again."),
]


def friendly_error(message) -> str:
    """Map any error text to a short plain-language sentence."""
    from backend.device_fallback import StudioUnavailable
    if isinstance(message, StudioUnavailable):
        return str(message)  # safe, typed, plain-words reason (no reinstall advice)
    text = str(message or "")
    for pattern, friendly in _FRIENDLY:
        if re.search(pattern, text, re.IGNORECASE):
            return friendly
    return GENERIC_ERROR


def first_run_checklist(ffmpeg_ok, espeak_ok, models_ok, storage_path):
    """Return the first-run items served by /api/health."""
    try:
        free = shutil.disk_usage(storage_path).free
    except OSError:
        free = 0
    gb = free / 1024**3
    disk_ok = free >= MIN_FREE_BYTES
    return [
        {"id": "ffmpeg", "label": "Audio tool (ffmpeg)", "ok": bool(ffmpeg_ok),
         "detail": "Found." if ffmpeg_ok else "Not found.",
         "action": "" if ffmpeg_ok else
         "Run Install Text2Audio.bat again, or install ffmpeg and restart Text2Audio."},
        {"id": "espeak", "label": "Pronunciation tool (espeak-ng)", "ok": bool(espeak_ok),
         "detail": "Found." if espeak_ok else "Not found.",
         "action": "" if espeak_ok else
         "Run Install Text2Audio.bat again, or install espeak-ng and restart Text2Audio."},
        {"id": "models", "label": "Voice model download", "ok": bool(models_ok),
         "detail": "Downloaded. Text2Audio works offline." if models_ok else "Voice models or English language package missing.",
         "action": "" if models_ok else
         "Double-click Install Text2Audio.bat to download the voice models and the English language package. It is a large one-time download and safe to run again; finished files are kept."},
        {"id": "disk", "label": "Free disk space", "ok": disk_ok,
         "detail": f"{gb:.1f} GB free." if disk_ok else f"Only {gb:.1f} GB free.",
         "action": "" if disk_ok else
         "Free up at least 2 GB on the drive where Text2Audio is stored."},
    ]
