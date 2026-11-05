"""Preview repair errors remain actionable without poisoning the render lock."""
import socket
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend import model_download as md
from tests.test_integration_seams import isolated_server_module


@pytest.mark.parametrize('failure_stage', ['constructor', 'inference'])
def test_missing_model_preview_is_json_and_releases_resources(tmp_path, monkeypatch, failure_stage):
    original_connect, original_dns = socket.socket.connect, socket.getaddrinfo
    def connect(sock, address):
        assert address[0] in ('127.0.0.1', '::1'), 'external network forbidden'
        return original_connect(sock, address)
    def dns(host, *args, **kwargs):
        assert host in ('127.0.0.1', '::1', 'localhost'), 'external DNS forbidden'
        return original_dns(host, *args, **kwargs)
    monkeypatch.setattr(socket.socket, 'connect', connect)
    monkeypatch.setattr(socket, 'getaddrinfo', dns)
    with isolated_server_module(tmp_path, monkeypatch) as server:
        closed = []
        def missing():
            # Real readiness implementation, empty owned cache, no model mocks.
            md.require_files(md.KOKORO_REPO, ['kokoro-v1_0.pth'])
        class MissingSynth:
            def preview(self, text):
                missing()
            def close(self):
                closed.append(True)
        def factory(*args):
            if failure_stage == 'constructor':
                missing()
            return MissingSynth()
        monkeypatch.setattr(server, 'SYNTH_FACTORY', factory)
        client = TestClient(server.app, raise_server_exceptions=False)
        for _ in range(2):
            response = client.post('/api/voice-preview', json={'voice': 'af_heart'})
            assert response.status_code == 409, response.text
            assert response.json()['error'] == 'model_unavailable'
            assert 'Install Text2Audio.bat' in response.json()['detail']
            assert 'Traceback' not in response.text and str(tmp_path) not in response.text
            assert not server._render_lock.locked()
        assert len(closed) == (2 if failure_stage == 'inference' else 0)
        class ReadySynth:
            def preview(self, text):
                return np.zeros(2400, dtype=np.float32)
            def close(self):
                closed.append(True)
        monkeypatch.setattr(server, 'SYNTH_FACTORY', lambda *a: ReadySynth())
        result = client.post('/api/voice-preview', json={'voice': 'af_heart'})
        assert result.status_code == 200 and result.content.startswith(b'RIFF')
        assert not server._render_lock.locked()
        unknown = client.post('/api/voice-preview', json={'voice': 'unknown-narrator'})
        assert unknown.status_code == 422

