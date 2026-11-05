"""Behavior assertions for the real server's test-owned storage configuration."""
import os
from pathlib import Path
from backend import model_download as md


def assert_server_owned_paths(server, root):
    root = Path(root).resolve()
    paths = [server.LIBRARY_DIR, server.VOICES_DIR, server.PRON_PATH,
             server.CONSENT_PATH, server.cache.base, server.voices.base,
             md.hub_cache()]
    paths += [os.environ[key] for key in (
        'HF_HOME', 'HF_HUB_CACHE', 'T2A_SETTINGS_PATH', 'T2A_LOG_DIR',
        'T2A_CACHE_DIR', 'T2A_VOICES_DIR',
        'T2A_PRON_PATH', 'T2A_CONSENT_PATH')]
    if os.environ.get('T2A_INSTALL_LOG'):
        paths.append(os.environ['T2A_INSTALL_LOG'])
    assert all(Path(p).resolve().is_relative_to(root) for p in paths), paths
