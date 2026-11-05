import pytest


@pytest.fixture(autouse=True)
def _reset_runtime_fallback():
    """Runtime CPU fallback is process-global state; never let it leak between tests."""
    from backend import device_fallback as df
    df.reset_runtime_fallback()
    yield
    df.reset_runtime_fallback()


@pytest.fixture(autouse=True)
def _owned_test_environment(tmp_path, monkeypatch, request):
    """Defaults cannot read host caches or write host data; tests may override them."""
    import socket
    import sys

    paths = {
        'HF_HOME': 'hf', 'HF_HUB_CACHE': 'hf/hub',
        'T2A_SETTINGS_PATH': 'settings.json', 'T2A_LIBRARY_DIR': 'library',
        'T2A_CACHE_DIR': 'cache', 'T2A_VOICES_DIR': 'voices',
        'T2A_PRON_PATH': 'pron.json', 'T2A_CONSENT_PATH': 'consent.json',
        'T2A_LOG_DIR': 't2a-logs',
    }
    for key, relative in paths.items():
        monkeypatch.setenv(key, str(tmp_path / relative))
    # An inherited explicit installer log takes precedence over T2A_LOG_DIR.
    monkeypatch.delenv('T2A_INSTALL_LOG', raising=False)
    server_test = request.module.__name__.rsplit('.', 1)[-1] in {
        'test_api', 'test_text2audio_voice_resolution', 'test_launch_checks',
        'test_device_fallback', 'test_runtime_fallback', 'test_studio_late_refusal',
        'test_integration_seams', 'test_preview_model_recovery',
    }
    previous = sys.modules.get('server') if server_test else None
    namespace = dict(vars(previous)) if previous is not None else None
    if server_test:
        for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY'):
            monkeypatch.setenv(key, '1')
        original_connect, original_dns = socket.socket.connect, socket.getaddrinfo
        def connect(sock, address):
            assert address[0] in ('127.0.0.1', '::1'), 'external test socket forbidden'
            return original_connect(sock, address)
        def dns(host, *args, **kwargs):
            assert host in ('127.0.0.1', '::1', 'localhost'), 'external test DNS forbidden'
            return original_dns(host, *args, **kwargs)
        monkeypatch.setattr(socket.socket, 'connect', connect)
        monkeypatch.setattr(socket, 'getaddrinfo', dns)
    try:
        yield
    finally:
        if server_test:
            # Undo test patches before restoring the previous namespace, otherwise
            # monkeypatch teardown could reinstall a temporary factory afterwards.
            monkeypatch.undo()
            if previous is None:
                sys.modules.pop('server', None)
            else:
                vars(previous).clear()
                vars(previous).update(namespace)
                sys.modules['server'] = previous
