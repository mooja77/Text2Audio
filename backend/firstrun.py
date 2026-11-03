"""First-run checklist and plain-language error messages (no raw stack text)."""
import re
import shutil

MIN_FREE_BYTES = 2 * 1024**3
GENERIC_ERROR = ("Something went wrong. Please try again. If it keeps happening, "
                 "check the setup checklist at the top of the page.")

_FRIENDLY = [
    (r"no space left|disk full", "Your disk is full. Free up some space and try again."),
    (r"ffmpeg", "A required audio tool is missing. Check the setup checklist at the top of the page."),
    (r"f5-tts|f5 worker|f5 synthesis",
     "Voice cloning is not available. Choose a built-in narrator, or see INSTALL.md to add cloning."),
    (r"timed out", "The voice engine took too long to respond. Try again, or try a shorter chapter."),
    (r"cancel", "The audiobook was cancelled."),
    (r"connection|urlopen|resolve|offline|max retries",
     "Text2Audio could not download the voice model. Connect to the internet for the first run and try again."),
]


def friendly_error(message) -> str:
    """Map any error text to a short plain-language sentence."""
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
         "detail": "Downloaded. Text2Audio works offline." if models_ok else "Not downloaded yet.",
         "action": "" if models_ok else
         "Connect to the internet and make your first audiobook. The download (a few hundred MB) happens once."},
        {"id": "disk", "label": "Free disk space", "ok": disk_ok,
         "detail": f"{gb:.1f} GB free." if disk_ok else f"Only {gb:.1f} GB free.",
         "action": "" if disk_ok else
         "Free up at least 2 GB on the drive where Text2Audio is stored."},
    ]
