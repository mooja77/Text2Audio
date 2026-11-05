"""Source checks for the web UI (no browser available offline)."""
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / 'web' / 'js'


def read(name):
    return (WEB / name).read_text(encoding='utf-8')


def test_health_can_be_refreshed_after_load_chunk_or_failure():
    app, create = read('app.js'), read('create.js')
    assert 'async refreshHealth()' in app and 'Create.refreshVoices()' in app
    assert 'Voices.syncClone()' in app
    assert create.count('T2A.refreshHealth()') >= 3


def test_voices_surfaces_safe_reasons_and_clean_badge():
    v = read('voices.js')
    assert 'Sample failed: ' in v and 'Clone failed: ' in v
    assert 'Clone failed — check the audio file' not in v
    assert '\ufffd' not in v and '\u25cf cloned' in v
