"""Actual constructor / chunk OOM -> CPU must stay coherent with health, default and guards."""
from tests.server_isolation import assert_server_owned_paths
import importlib
import json

import pytest
from fastapi.testclient import TestClient

from backend import device_fallback as df


class Synth:
    fail_init = False
    fail_chunk = False

    def __init__(self, voice, lang_code, speed, device):
        self.device = device
        if device == 'cuda' and Synth.fail_init:
            raise RuntimeError('CUDA out of memory. Tried to allocate 2 GiB')

    def synth_chunk(self, text):
        if self.device == 'cuda' and Synth.fail_chunk:
            raise RuntimeError('CUDA out of memory. Tried to allocate 2 GiB')
        return self.device


@pytest.fixture(autouse=True)
def _gpu(monkeypatch, tmp_path):
    Synth.fail_init = Synth.fail_chunk = False
    monkeypatch.setattr(df, '_cuda_free_gb', lambda torch_module=None: 12.0)
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({'gpu_usable': True}), encoding='utf-8')
    monkeypatch.setenv('T2A_SETTINGS_PATH', str(path))
    monkeypatch.delenv('T2A_DEVICE', raising=False)
    return str(path)


def test_constructor_oom_keeps_cpu_after_recheck(_gpu):
    assert df.resolve_device({}, _gpu).studio is True
    Synth.fail_init = True
    assert df.build_kokoro('af_heart', 1.0, 'cuda', Synth).device == 'cpu'
    for _ in range(2):  # a later eligibility recheck must not flip back to CUDA
        d = df.resolve_device({}, _gpu)
        assert d.device == 'cpu' and not d.studio and d.default_voice == 'af_heart'
        assert 'ran out of memory' in d.reason
    assert d.health_fields()['engines'] == {'default': 'kokoro', 'available': ['kokoro']}


def test_chunk_oom_keeps_cpu_after_recheck(_gpu):
    synth = df.build_kokoro('af_heart', 1.0, 'cuda', Synth)
    assert df.resolve_device({}, _gpu).studio is True
    Synth.fail_chunk = True
    assert synth.synth_chunk('x') == 'cpu'
    d = df.resolve_device({}, _gpu)
    assert d.device == 'cpu' and not d.studio and d.reason


def test_explicit_cpu_always_wins_and_reset_clears(_gpu):
    Synth.fail_init = True
    df.build_kokoro('af_heart', 1.0, 'cuda', Synth)
    assert df.resolve_device({'T2A_DEVICE': 'cpu'}, _gpu).reason == df.FORCED_CPU
    df.reset_runtime_fallback()
    assert df.resolve_device({}, _gpu).studio is True


def test_other_errors_do_not_set_fallback(_gpu):
    Synth.fail_init = True
    Synth.fail_chunk = False
    try:
        class Bad(Synth):
            def __init__(self, *a, **k):
                raise RuntimeError('bad weights')
        df.build_kokoro('af_heart', 1.0, 'cuda', Bad)
    except RuntimeError:
        pass
    assert df.runtime_cpu_reason() is None


def test_health_default_and_guards_follow_actual_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv('T2A_LIBRARY_DIR', str(tmp_path / 'library'))
    import server
    importlib.reload(server)
    assert_server_owned_paths(server, tmp_path)
    monkeypatch.setattr(server, 'studio_engine_available', lambda: True)
    with TestClient(server.app) as c:
        body = c.get('/api/health').json()
        assert body['device'] == 'cuda' and body['defaultVoice'] == 'studio_narrator'
        Synth.fail_init = True
        df.build_kokoro('af_heart', 1.0, 'cuda', Synth)
        body = c.get('/api/health').json()
        assert body['device'] == 'cpu' and body['defaultVoice'] == 'af_heart'
        assert body['studio']['available'] is False and body['cloning']['reason']
        assert body['voiceCloning'] is False
        r = c.post('/api/render', json={'bookText': '## A\n\nhi', 'voice': 'studio_narrator'})
        assert r.status_code == 409 and r.json()['detail'] == body['studio']['reason']
        r = c.post('/api/voices/clone', files={'audio': ('r.wav', b'x', 'audio/wav')}, data={'name': 'N'})
        assert r.status_code == 409 and r.json()['error'] == 'studio_unavailable'
