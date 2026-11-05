r"""Install glue that scripts/install.ps1 calls once Python exists.

Run it as a script, not with -m (the project is not installed yet):
    .venv\Scripts\python.exe scripts\install_support.py --check

Stages (each prints plain words, appends to the quoted launch log, returns 0 or 1):
    --stage pre        graphics-card check with nvidia-smi (before PyTorch)
    --stage prepare    CUDA/free-memory check, model download, English language package
    --stage post       final graphics-card check after model/language preparation
    --stage verify     tools + full offline readiness; this gates success
    --check            pre, prepare, post, verify in order
    --winget-guidance  manual install paths when winget is missing
Re-running is safe: verified files and installed packages are skipped.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend import hardware, launch_checks, model_download as md, offline  # noqa: E402

LANGUAGE_URL = ("https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/"
                "en_core_web_sm-3.8.0-py3-none-any.whl#sha256="
                "1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85")
ESPEAK_DLL = r"C:\Program Files\eSpeak NG\libespeak-ng.dll"
RERUN = ("Nothing is lost. Check your internet connection, then double-click "
         "'Install Text2Audio.bat' again. It skips everything already finished and "
         "carries on where it stopped.")
WINGET_GUIDANCE = (
    "Windows' installer tool (winget) was not found, so Text2Audio cannot install some tools "
    "for you. Your installed tools and settings are untouched. Install them by hand, then "
    "double-click 'Install Text2Audio.bat' again:\n"
    "  - Python 3.12: https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH')\n"
    "  - ffmpeg: https://www.gyan.dev/ffmpeg/builds/ (add its bin folder to PATH)\n"
    "  - espeak-ng: https://github.com/espeak-ng/espeak-ng/releases (the Windows .msi)")


class Reporter:
    def __init__(self, out=print):
        self.out, self.lines = out, []

    def say(self, text):
        self.lines.extend(text.splitlines())
        self.out(text)


def _run(cmd):
    done = subprocess.run(cmd, capture_output=True, text=True)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def missing_tools(which=shutil.which, exists=os.path.exists):
    out = []
    if not which("ffmpeg"):
        out.append("ffmpeg")
    if not (which("espeak-ng") or exists(ESPEAK_DLL) or os.environ.get("PHONEMIZER_ESPEAK_PATH")):
        out.append("espeak-ng")
    return out


def stage_hardware(rep, post, settings=hardware.DEFAULT_SETTINGS_PATH, **kw):
    report = hardware.check_and_save(settings, post_install=post, **kw)
    rep.say(("Graphics card check (after setup): " if post else "Graphics card check: ") + report.message)
    return report.usable


def make_progress(rep, clock=time.monotonic, every=5.0):
    state = {"t": -1e9, "pct": -1}

    def show(p):
        now = clock()
        if p["percent"] == 100 or p["percent"] >= state["pct"] + 2 or now - state["t"] >= every:
            state.update(t=now, pct=p["percent"])
            rep.say("Downloading voice models: %.0f MB of %.0f MB (%d%%) - %s" % (
                p["done_mb"], p["total_mb"], p["percent"], p["file"]))
    return show


def stage_models(rep, gpu_usable, install=md.install):
    rep.say("Preparing the voice models (a large one-time download; safe to rerun).")
    try:
        result = install(gpu_usable=gpu_usable, include_chatterbox=md.want_chatterbox(os.environ, gpu_usable),
                         progress=make_progress(rep))
    except (md.DiskSpaceError, md.DownloadError, md.InstallBusy) as exc:
        rep.say("The voice models are not ready: %s\n%s" % (exc, RERUN))
        return False
    rep.say("Voice model files verified (%d reused, %d downloaded)." % (
        len(result["reused"]), len(result["downloaded"])))
    return True


def stage_language(rep, run=_run, ready=md.language_ready):
    probe = [sys.executable, "-c", "import spacy; spacy.load('en_core_web_sm')"]
    if ready() and run(probe)[0] == 0:
        rep.say("English language package (en_core_web_sm %s) is already installed." % md.LANGUAGE_VERSION)
        return True
    rep.say("Installing the English language package (en_core_web_sm %s, checksum-verified)." % md.LANGUAGE_VERSION)
    code, text = run([sys.executable, "-m", "pip", "install", LANGUAGE_URL])
    rep.lines.append(text[-2000:])
    if code != 0 or not ready() or run(probe)[0] != 0:
        rep.say("The English language package could not be installed or loaded.\n" + RERUN)
        return False
    rep.say("English language package installed and loads offline.")
    return True


def stage_prepare(rep, **kw):
    gpu = stage_hardware(rep, True, **kw)  # CUDA usability and free memory choose the Studio download
    return stage_models(rep, gpu) and stage_language(rep)


def stage_verify(rep, tools=missing_tools, cached=offline.models_cached):
    gone = tools()
    if gone:
        rep.say("Still missing: %s. Text2Audio is not ready. %s" % (", ".join(gone), WINGET_GUIDANCE))
        return False
    gpu = hardware.gpu_usable_from_settings(hardware.DEFAULT_SETTINGS_PATH)
    repos = [md.KOKORO_REPO] + ([md.CHATTERBOX_REPO] if md.runtime_needs_chatterbox(os.environ, gpu) else [])
    if not cached(os.environ, tuple(repos)):
        rep.say("The voice models or language package are not fully ready for offline use.\n" + RERUN)
        return False
    rep.say("Everything is ready for offline use.")
    return True


def main(argv=None, out=print, env=None, **deps):
    ap = argparse.ArgumentParser(description="Text2Audio install helper (called by install.ps1).")
    ap.add_argument("--check", action="store_true", help="run every stage in order")
    ap.add_argument("--stage", choices=["pre", "prepare", "post", "verify"])
    ap.add_argument("--winget-guidance", action="store_true")
    args = ap.parse_args(argv)
    rep = Reporter(out)
    try:
        if args.winget_guidance:
            rep.say(WINGET_GUIDANCE)
            ok = True
        else:
            stages = {"pre": lambda: stage_hardware(rep, False) or True,
                      "prepare": lambda: stage_prepare(rep),
                      "post": lambda: stage_hardware(rep, True) or True,
                      "verify": lambda: stage_verify(rep)}
            names = ["pre", "prepare", "post", "verify"] if args.check else [args.stage] if args.stage else []
            if not names:
                ap.error("choose --check, --stage or --winget-guidance")
            ok = True
            for name in names:
                ok = deps.get(name, stages[name])()
                if not ok:
                    break
    except Exception as exc:  # plain words, never a raw traceback
        rep.say("Setup hit an unexpected problem (%s: %s).\n%s" % (type(exc).__name__, exc, RERUN))
        ok = False
    path, written = launch_checks.write_log(rep.lines, env)
    out(launch_checks._log_line(path, written))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
