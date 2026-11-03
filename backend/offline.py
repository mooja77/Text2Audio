"""Force the Hugging Face libraries offline once the models are cached.

HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE are read when huggingface_hub and
transformers are imported, so configure_at_startup() has to run before any
import that pulls them in. This module must never import those libraries.
"""
import os

KOKORO_REPOS = ("hexgrad/Kokoro-82M",)
OFFLINE_VARS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY")


def _hub_cache(env) -> str:
    if env.get("HF_HUB_CACHE"):
        return env["HF_HUB_CACHE"]
    home = env.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    return os.path.join(home, "hub")


def models_cached(env=os.environ, repos=KOKORO_REPOS) -> bool:
    """True only if every repo has at least one snapshot in the HF cache."""
    hub = _hub_cache(env)
    for repo in repos:
        snaps = os.path.join(hub, "models--" + repo.replace("/", "--"), "snapshots")
        try:
            if not os.listdir(snaps):
                return False
        except OSError:
            return False
    return True


def configure_at_startup(env=os.environ, repos=KOKORO_REPOS) -> dict:
    """Go offline if the models are cached; otherwise stay online for the first download.

    Returns the variables it set (empty when left online)."""
    if not models_cached(env, repos):
        return {}
    for name in OFFLINE_VARS:
        env[name] = "1"
    return {name: "1" for name in OFFLINE_VARS}
