"""Force the Hugging Face libraries offline once the models are cached.

HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE are read when huggingface_hub and
transformers are imported, so configure_at_startup() has to run before any
import that pulls them in. This module must never import those libraries at
module level.

Kokoro downloads each narrator voice (``voices/<id>.pt``) the first time it is
used. When *we* forced offline mode, ensure_voice_available() fetches a voice
that is not cached yet, once, so choosing a new narrator still works on a
connected PC. If the user set HF_HUB_OFFLINE themselves, it is respected.
"""
import os

from pipeline.engines import CHATTERBOX_FILES, CHATTERBOX_REPO

KOKORO_REPO = "hexgrad/Kokoro-82M"
# repo -> files that must be in a snapshot before we treat the repo as cached.
REQUIRED_FILES = {
    KOKORO_REPO: ("config.json", "kokoro-v1_0.pth"),
    CHATTERBOX_REPO: CHATTERBOX_FILES,
}
KOKORO_REPOS = (KOKORO_REPO,)
OFFLINE_VARS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY")

# True only when configure_at_startup() turned offline mode on in this process.
_forced = False


def _hub_cache(env) -> str:
    if env.get("HF_HUB_CACHE"):
        return env["HF_HUB_CACHE"]
    home = env.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    return os.path.join(home, "hub")


def _snapshots(env, repo):
    snaps = os.path.join(_hub_cache(env), "models--" + repo.replace("/", "--"), "snapshots")
    try:
        return [os.path.join(snaps, s) for s in os.listdir(snaps)]
    except OSError:
        return []


def models_cached(env=None, repos=KOKORO_REPOS) -> bool:
    """True only if every repo has a snapshot holding its required files."""
    env = os.environ if env is None else env
    for repo in repos:
        required = REQUIRED_FILES.get(repo, ())
        if not any(all(os.path.exists(os.path.join(s, f)) for f in required) for s in _snapshots(env, repo)):
            return False
    return True


def voice_cached(voice: str, env=None) -> bool:
    env = os.environ if env is None else env
    return any(os.path.exists(os.path.join(s, "voices", f"{voice}.pt")) for s in _snapshots(env, KOKORO_REPO))


def configure_at_startup(env=None, repos=KOKORO_REPOS) -> dict:
    """Go offline if the models are cached; otherwise stay online for the first download.

    Returns the variables it set (empty when left online)."""
    global _forced
    env = os.environ if env is None else env
    if not models_cached(env, repos):
        return {}
    if any(env.get(name) for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")):
        return {}  # the user chose an offline setting themselves; leave it alone
    for name in OFFLINE_VARS:
        env[name] = "1"
    if env is os.environ:
        _forced = True
    return {name: "1" for name in OFFLINE_VARS}


def ensure_voice_available(voice: str, download=None, hub_constants=None) -> bool:
    """Fetch an uncached narrator voice once if *we* forced offline mode.

    Returns True if a download was attempted. A failed download (no network)
    raises the library's own error, which the render reports as before."""
    if not _forced or voice_cached(voice):
        return False
    if hub_constants is None:
        from huggingface_hub import constants as hub_constants
    if download is None:
        from huggingface_hub import hf_hub_download as download
    constants = hub_constants
    previous = constants.HF_HUB_OFFLINE
    constants.HF_HUB_OFFLINE = False  # read per call by huggingface_hub
    try:
        download(repo_id=KOKORO_REPO, filename=f"voices/{voice}.pt")
    finally:
        constants.HF_HUB_OFFLINE = previous
    return True
