"""Force the Hugging Face libraries offline once the pinned models are fully ready.

HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE are read when huggingface_hub and
transformers are imported, so configure_at_startup() has to run before any
import that pulls them in. This module must never import those libraries at
module level (backend.model_download is stdlib-only).

Readiness is the installer's: every pinned file of the repo is checked by exact
size and digest in the pinned snapshot directory, and for Kokoro the spaCy
language model must be installed too. Anything else (partial, unpinned or
corrupt snapshots) stays online. A user's own offline setting is respected.
"""
import os

from pipeline.engines import CHATTERBOX_FILES, CHATTERBOX_REPO
from backend import model_download as md

KOKORO_REPO = "hexgrad/Kokoro-82M"
REQUIRED_FILES = {
    KOKORO_REPO: ("config.json", "kokoro-v1_0.pth"),
    CHATTERBOX_REPO: CHATTERBOX_FILES,
}
KOKORO_REPOS = (KOKORO_REPO,)
OFFLINE_VARS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY")

# True only when configure_at_startup() turned offline mode on in this process.
_forced = False
# (root, repo) -> stat signature of a fully digest-verified repo (avoids rehashing on every call).
_VERIFIED = {}


def _hub_cache(env) -> str:
    return md.hub_cache(env)


def _snapshots(env, repo):
    snaps = os.path.join(_hub_cache(env), "models--" + repo.replace("/", "--"), "snapshots")
    try:
        return [os.path.join(snaps, s) for s in os.listdir(snaps)]
    except OSError:
        return []


def _repo_ok(root, repo) -> bool:
    try:
        sig = tuple((st.st_size, st.st_mtime_ns) for st in (
            os.stat(md.local_path(root, repo, s.rel)) for s in md.MANIFEST[repo][1]))
    except OSError:
        _VERIFIED.pop((root, repo), None)
        return False
    if _VERIFIED.get((root, repo)) == sig:
        return True
    if md.repo_ready(root, repo):
        _VERIFIED[(root, repo)] = sig
        return True
    _VERIFIED.pop((root, repo), None)
    return False


def models_cached(env=None, repos=KOKORO_REPOS) -> bool:
    """True only if every repo is fully present and verified in its pinned snapshot
    (and, for Kokoro, the correct language model is installed)."""
    env = os.environ if env is None else env
    if KOKORO_REPO in repos and not md.language_ready():
        return False
    root = md.hub_cache(env)
    return all(repo in md.MANIFEST and _repo_ok(root, repo) for repo in repos)


def voice_cached(voice: str, env=None) -> bool:
    env = os.environ if env is None else env
    rel = f"voices/{voice}.pt"
    spec = next((s for s in md.MANIFEST[KOKORO_REPO][1] if s.rel == rel), None)
    return spec is not None and md.is_valid(md.local_path(md.hub_cache(env), KOKORO_REPO, rel), spec)


def configure_at_startup(env=None, repos=KOKORO_REPOS) -> dict:
    """Go offline if the pinned models are fully ready; otherwise stay online.

    Returns the variables it set (empty when left online)."""
    global _forced
    env = os.environ if env is None else env
    if any(env.get(name) for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")):
        return {}  # the user chose an offline setting themselves; leave it alone
    if not repos or not models_cached(env, repos):
        return {}
    for name in OFFLINE_VARS:
        env[name] = "1"
    if env is os.environ:
        _forced = True
    return {name: "1" for name in OFFLINE_VARS}


def ensure_voice_available(voice: str, download=None, hub_constants=None) -> bool:
    """Fetch an uncached narrator voice once (pinned revision) if *we* forced offline mode.

    Returns True if a download was attempted."""
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
        download(repo_id=KOKORO_REPO, filename=f"voices/{voice}.pt", revision=md.KOKORO_REV)
    finally:
        constants.HF_HUB_OFFLINE = previous
    return True
