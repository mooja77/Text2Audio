"""CPU fallback tests. torch and settings are mocked: no GPU is needed."""
import io
import json
import importlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import device_fallback as df


def fake_torch(free_gb=None, total_gb=24):
    cuda = SimpleNamespace(is_available=lambda: free_gb is not None,
                           mem_get_info=lambda i: (int((free_gb or 0) * 1024**3), total_gb * 1024**3))
    return SimpleNamespace(cuda=cuda)


def settings(tmp_path, usable):
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({'gpu_usable': usable}), encoding='utf-8')
    return str(path)


def test_no_usable_gpu_means_cpu_and_kokoro_default(tmp_path):
    d = df.resolve_device({}, settings(tmp_path, False))
    assert d.device == 'cpu' and d.studio is False and d.default_voice == 'af_heart'
    assert 'NVIDIA' in d.reason and 'processor' in d.reason
    f = d.health_fields()
    assert f['engines'] == {'default': 'kokoro', 'available': ['kokoro']}
    assert f['studio']['available'] is False and f['cloning']['reason'] == d.reason


def test_missing_settings_is_cpu(tmp_path):
    assert df.resolve_device({}, str(tmp_path / 'none.json')).device == 'cpu'


def test_explicit_cpu_beats_nvidia_pc_with_chatterbox(tmp_path):
    d = df.resolve_device({'T2A_DEVICE': 'cpu'}, settings(tmp_path, True),
                          torch_module=fake_torch(24), engine_installed=True)
    assert d.device == 'cpu' and not d.studio and d.default_voice == 'af_heart'
    assert 'T2A_DEVICE' in d.reason


def test_usable_gpu_enables_studio(tmp_path):
    d = df.resolve_device({}, settings(tmp_path, True), torch_module=fake_torch(12))
    assert d.device == 'cuda' and d.studio and d.default_voice == 'studio_narrator'
    assert d.health_fields()['engines']['available'] == ['kokoro', 'chatterbox']


def test_forced_cuda_falls_back_when_unusable_or_low_memory(tmp_path):
    env = {'T2A_DEVICE': 'cuda'}
    assert df.resolve_device(env, torch_module=fake_torch(None)).device == 'cpu'
    low = df.resolve_device(env, torch_module=fake_torch(4.9))
    assert low.device == 'cpu' and not low.studio and '4.9' in low.reason
    assert df.resolve_device(env, torch_module=fake_torch(5.0)).studio is True


def test_settings_say_usable_but_memory_is_gone_at_load(tmp_path):
    d = df.resolve_device({}, settings(tmp_path, True), torch_module=fake_torch(2))
    assert d.device == 'cpu' and not d.studio


def test_optin_download_never_enables_cpu_studio(tmp_path):
    d = df.resolve_device({'T2A_DOWNLOAD_CHATTERBOX': '1'}, settings(tmp_path, False))
    assert d.device == 'cpu' and not d.studio
    d = df.resolve_device({'T2A_DOWNLOAD_CHATTERBOX': '1', 'T2A_DEVICE': 'cpu'}, settings(tmp_path, True),
                          torch_module=fake_torch(24))
    assert not d.studio


def test_missing_engine_is_explained(tmp_path):
    d = df.resolve_device({}, settings(tmp_path, True), torch_module=fake_torch(12), engine_installed=False)
    assert d.device == 'cuda' and not d.studio and 'not installed' in d.reason


def test_worker_device_gives_reason_on_cpu(tmp_path):
    device, reason = df.worker_device({'T2A_DEVICE': 'cpu'})
    assert device is None and 'T2A_DEVICE' in reason
    assert df.worker_device({'T2A_DEVICE': 'cuda'}, fake_torch(8)) == ('cuda', '')


class FakeSynth:
    fail_init = False
    fail_chunk = False
    error = 'CUDA out of memory. Tried to allocate 2 GiB'

    def __init__(self, voice, lang_code, speed, device):
        self.device = device
        if device == 'cuda' and FakeSynth.fail_init:
            raise RuntimeError(FakeSynth.error)

    def synth_chunk(self, text):
        if self.device == 'cuda' and FakeSynth.fail_chunk:
            raise RuntimeError(FakeSynth.error)
        return self.device


@pytest.fixture(autouse=True)
def _reset_fake():
    FakeSynth.fail_init = FakeSynth.fail_chunk = False
    FakeSynth.error = 'CUDA out of memory. Tried to allocate 2 GiB'


def test_kokoro_oom_at_load_retries_on_cpu():
    FakeSynth.fail_init = True
    assert df.build_kokoro('af_heart', 1.0, 'cuda', FakeSynth).device == 'cpu'


def test_kokoro_oom_mid_render_switches_to_cpu():
    FakeSynth.fail_chunk = True
    synth = df.build_kokoro('af_heart', 1.0, 'cuda', FakeSynth)
    assert synth.device == 'cuda'
    assert synth.synth_chunk('hi') == 'cpu' and synth.device == 'cpu'
    assert synth.synth_chunk('again') == 'cpu'


def test_other_errors_are_not_hidden():
    FakeSynth.fail_init, FakeSynth.error = True, 'bad weights'
    with pytest.raises(RuntimeError, match='bad weights'):
        df.build_kokoro('af_heart', 1.0, 'cuda', FakeSynth)


def test_engine_worker_refusal_becomes_plain_error(monkeypatch):
    import pipeline.clone_synth as cs

    class Proc:
        stdin = io.StringIO()

        def __init__(self):
            self.stdout = io.StringIO(json.dumps({'unavailable': 'No graphics card. Use a fast voice.'}) + '\n')

        def poll(self):
            return None

        def kill(self):
            pass

    monkeypatch.setattr(cs.subprocess, 'Popen', lambda *a, **k: Proc())
    with pytest.raises(df.StudioUnavailable, match='No graphics card'):
        cs._start_worker()


@pytest.fixture()
def make_client(tmp_path, monkeypatch):
    def make(usable=False, forced=None):
        monkeypatch.setenv('T2A_LIBRARY_DIR', str(tmp_path / 'library'))
        monkeypatch.setenv('T2A_SETTINGS_PATH', settings(tmp_path, usable))
        if forced:
            monkeypatch.setenv('T2A_DEVICE', forced)
        else:
            monkeypatch.delenv('T2A_DEVICE', raising=False)
        import server
        importlib.reload(server)
        monkeypatch.setattr(server, 'studio_engine_available', lambda: True)
        return server, TestClient(server.app)
    return make


def test_health_on_cpu_reports_kokoro_and_plain_reasons(make_client):
    server, client = make_client(usable=False)
    with client as c:
        body = c.get('/api/health').json()
        assert body['device'] == 'cpu' and body['defaultVoice'] == 'af_heart'
        assert body['engines'] == {'default': 'kokoro', 'available': ['kokoro']}
        assert body['studioVoices'] is False and body['voiceCloning'] is False
        assert body['studio']['available'] is False and body['studio']['reason']
        assert body['cloning']['reason'] == body['studio']['reason']
        assert any(v['id'] == 'studio_narrator' for v in c.get('/api/voices').json())


def test_forced_cpu_overrides_nvidia_pc_everywhere(make_client, monkeypatch):
    server, client = make_client(usable=True, forced='cpu')
    with client as c:
        body = c.get('/api/health').json()
        assert body['device'] == 'cpu' and body['defaultVoice'] == 'af_heart'
        assert body['studio']['available'] is False and 'T2A_DEVICE' in body['studio']['reason']
        book = {'bookText': '## A\n\nhi'}
        r = c.post('/api/render', json={**book, 'voice': 'studio_narrator'})
        assert r.status_code == 409 and r.json()['error'] == 'studio_unavailable'
        assert r.json()['detail'] == body['studio']['reason']
        assert c.post('/api/voice-preview', json={'voice': 'studio_narrator'}).status_code == 409
        files = {'audio': ('r.wav', b'x', 'audio/wav')}
        r = c.post('/api/voices/clone', files=files, data={'name': 'N'})
        assert r.status_code == 409 and r.json()['detail'] == body['studio']['reason']
        assert c.post('/api/render', json={**book, 'voice': 'nope'}).status_code == 422
