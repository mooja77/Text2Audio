"""Seam tests between the five modules (settings, models, device, launcher, orchestration).

Everything is mocked: no GPU, no network, no real ports, no PowerShell.
"""
import importlib
import io
import json
import logging
import os
import socket
import subprocess
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest

from backend import device_fallback as df
from backend import hardware
from backend import launch_checks as lc
from backend import model_download as md
from backend import offline as off
from pipeline import engines
from pipeline.engines import chatterbox_engine as ce
from pipeline.synth import PRESET_VOICES

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import install_support as ins  # noqa: E402

BIG = lambda p: types.SimpleNamespace(free=10 ** 12)
NOSLEEP = lambda s: None
WEIGHTS = bytes(range(256)) * 20


# ---- helpers -------------------------------------------------------------
def fake_torch(free_gb):
    cuda = types.SimpleNamespace(
        is_available=lambda: free_gb is not None,
        mem_get_info=lambda i: (int((free_gb or 0) * 1024 ** 3), 24 * 1024 ** 3))
    return types.SimpleNamespace(cuda=cuda)


def smi(free_mib):
    out = 'Card, 24576, %d\n' % free_mib
    return lambda cmd, **kw: types.SimpleNamespace(returncode=0, stdout=out, stderr='')


def settings_file(tmp_path, free_mib):
    path = tmp_path / 'settings.json'
    hardware.check_and_save(path, run=smi(free_mib))
    return path


def spec(rel, data):
    import hashlib
    return md.Spec(rel, len(data), hashlib.sha256(data).hexdigest())


def patch_manifest(monkeypatch, voices=('af_heart',)):
    kokoro = {'config.json': b'{}', 'kokoro-v1_0.pth': WEIGHTS}
    kokoro.update({'voices/%s.pt' % v: b'v:' + v.encode() for v in voices})
    cb = {n: b'cb:' + n.encode() for n in engines.CHATTERBOX_FILES}
    monkeypatch.setattr(md, 'MANIFEST', {
        md.KOKORO_REPO: (md.KOKORO_REV, tuple(spec(r, b) for r, b in kokoro.items())),
        md.CHATTERBOX_REPO: (engines.CHATTERBOX_REVISION, tuple(spec(r, b) for r, b in cb.items()))})
    return kokoro, cb


class Resp:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body, self.pos = status, headers, body, 0

    def read(self, n):
        chunk = self.body[self.pos:self.pos + n]
        self.pos += len(chunk)
        return chunk

    def close(self):
        pass


class Server:
    def __init__(self, files):
        self.files, self.calls = files, []

    def __call__(self, url, headers):
        self.calls.append((url, dict(headers)))
        name = url.split('/resolve/', 1)[1].split('/', 1)[1]
        data, start, status = self.files[name], 0, 200
        rng = headers.get('Range')
        if rng:
            start, status = int(rng.split('=')[1].rstrip('-')), 206
        hdr = {'ETag': 'e-' + name, 'Content-Length': str(len(data) - start)}
        if status == 206:
            hdr['Content-Range'] = 'bytes %d-%d/%d' % (start, len(data) - 1, len(data))
        return Resp(status, hdr, data[start:])

    def names(self):
        return [u.split('/resolve/', 1)[1].split('/', 1)[1] for u, _ in self.calls]


def do_install(root, srv, **kw):
    kw.setdefault('include_chatterbox', False)
    return md.install(root=str(root), opener=srv, sleep=NOSLEEP, disk_usage=BIG, **kw)


@pytest.fixture()
def no_sockets(monkeypatch):
    def deny(*a, **k):
        raise AssertionError('network access attempted')
    monkeypatch.setattr(socket, 'socket', deny)
    monkeypatch.setattr(socket, 'create_connection', deny)
    monkeypatch.setattr(socket, 'getaddrinfo', deny)


# ---- I-1 settings -> I-3 device fallback and I-2 Chatterbox gating -------
def test_detected_gpu_settings_drive_device_choice(tmp_path):
    path = settings_file(tmp_path, 20480)
    d = df.resolve_device({}, str(path), torch_module=fake_torch(12))
    assert d.device == 'cuda' and d.studio
    assert df.resolve_device({'T2A_SETTINGS_PATH': str(path)}, torch_module=fake_torch(12)).studio
    busy = settings_file(tmp_path, 2048)
    d = df.resolve_device({}, str(busy), torch_module=fake_torch(24))
    assert d.device == 'cpu' and not d.studio and 'free' in d.reason.lower()


def test_installed_chatterbox_plus_explicit_cpu_override_stays_cpu(tmp_path):
    path = settings_file(tmp_path, 20480)
    d = df.resolve_device({'T2A_DEVICE': 'cpu'}, str(path), torch_module=fake_torch(24),
                          engine_installed=True)
    assert d.device == 'cpu' and not d.studio and d.default_voice == 'af_heart'
    assert 'T2A_DEVICE' in d.reason


def test_settings_gate_chatterbox_download_and_runtime(tmp_path):
    usable = hardware.gpu_usable_from_settings(settings_file(tmp_path, 20480))
    assert usable is True
    assert md.want_chatterbox({}, usable) and md.runtime_needs_chatterbox({}, usable)
    assert not md.runtime_needs_chatterbox({}, usable, device='cpu')
    assert not md.runtime_needs_chatterbox({'T2A_DEVICE': 'cpu'}, usable)
    unusable = hardware.gpu_usable_from_settings(settings_file(tmp_path, 2048))
    assert unusable is False
    assert not md.want_chatterbox({}, unusable) and not md.runtime_needs_chatterbox({}, unusable)
    # opt-in prefetch downloads Chatterbox but never makes the CPU runtime need it
    opt = {'T2A_DOWNLOAD_CHATTERBOX': '1'}
    assert md.want_chatterbox(opt, False) and not md.runtime_needs_chatterbox(opt, False)


# ---- I-2 resume / disk-check idempotency ----------------------------------
def test_disk_failure_then_rerun_then_noop_needs_no_disk_or_network(tmp_path, monkeypatch, no_sockets):
    kokoro, _ = patch_manifest(monkeypatch)
    srv = Server(kokoro)
    with pytest.raises(md.DiskSpaceError):
        md.install(root=str(tmp_path), opener=srv, sleep=NOSLEEP, include_chatterbox=False,
                   disk_usage=lambda p: types.SimpleNamespace(free=100))
    assert srv.calls == []
    assert not os.path.exists(md.local_path(str(tmp_path), md.KOKORO_REPO, 'kokoro-v1_0.pth'))
    rep = do_install(tmp_path, srv)
    assert sorted(rep['downloaded']) == sorted(kokoro) and md.kokoro_ready(str(tmp_path))

    def boom(*a, **k):
        raise AssertionError('must not be called when nothing is missing')
    again = md.install(root=str(tmp_path), opener=boom, sleep=NOSLEEP, disk_usage=boom,
                       include_chatterbox=False)
    assert again['downloaded'] == [] and sorted(again['reused']) == sorted(kokoro)


def test_partial_file_resumes_with_range_and_validator(tmp_path, monkeypatch, no_sockets):
    kokoro, _ = patch_manifest(monkeypatch)
    s = next(x for x in md.MANIFEST[md.KOKORO_REPO][1] if x.rel == 'kokoro-v1_0.pth')
    part, meta = md._part_paths(str(tmp_path), md.KOKORO_REPO, s.rel)
    os.makedirs(os.path.dirname(part), exist_ok=True)
    with open(part, 'wb') as f:
        f.write(WEIGHTS[:2000])
    with open(meta, 'w') as f:
        json.dump({'size': s.size, 'digest': s.digest, 'etag': 'e-' + s.rel}, f)
    srv = Server(kokoro)
    do_install(tmp_path, srv)
    calls = {n: h for n, (_, h) in zip(srv.names(), srv.calls)}
    assert calls['kokoro-v1_0.pth'] == {'Range': 'bytes=2000-', 'If-Range': 'e-kokoro-v1_0.pth'}
    assert calls['config.json'] == {}
    assert md.kokoro_ready(str(tmp_path))


def test_cached_truncation_and_same_size_corruption_are_repaired(tmp_path, monkeypatch, no_sockets):
    kokoro, _ = patch_manifest(monkeypatch)
    do_install(tmp_path, Server(kokoro))
    final = md.local_path(str(tmp_path), md.KOKORO_REPO, 'kokoro-v1_0.pth')
    with open(final, 'wb') as f:
        f.write(WEIGHTS[:len(WEIGHTS) // 2])  # truncated
    assert not md.kokoro_ready(str(tmp_path))
    srv = Server(kokoro)
    rep = do_install(tmp_path, srv)
    assert rep['repaired'] == ['kokoro-v1_0.pth'] and srv.names() == ['kokoro-v1_0.pth']
    bad = bytearray(WEIGHTS)
    bad[0] ^= 1
    with open(final, 'wb') as f:
        f.write(bytes(bad))  # same size, wrong digest
    assert not md.kokoro_ready(str(tmp_path))
    assert md.repo_ready(str(tmp_path), md.KOKORO_REPO) is False
    srv = Server(kokoro)
    assert do_install(tmp_path, srv)['repaired'] == ['kokoro-v1_0.pth']
    assert md.kokoro_ready(str(tmp_path))


def test_default_transport_is_urllib_with_pinned_urls_and_progress(tmp_path, monkeypatch, no_sockets):
    kokoro, _ = patch_manifest(monkeypatch)
    seen = []

    def fake_urlopen(req, timeout=None):
        seen.append((req.full_url, req.get_header('User-agent'), timeout))
        name = req.full_url.split('/resolve/', 1)[1].split('/', 1)[1]
        body = kokoro[name]
        r = Resp(200, {'Content-Length': str(len(body)), 'ETag': 'e'}, body)
        return r

    monkeypatch.setattr(md.urllib.request, 'urlopen', fake_urlopen)
    progress = []
    md.install(root=str(tmp_path), include_chatterbox=False, progress=progress.append,
               sleep=NOSLEEP, disk_usage=BIG)
    prefix = 'https://huggingface.co/hexgrad/Kokoro-82M/resolve/%s/' % md.KOKORO_REV
    assert len(seen) == len(kokoro)
    assert all(u.startswith(prefix) and ua == 'text2audio-model-download' and t == 60
               for u, ua, t in seen)
    done = [p['done_bytes'] for p in progress]
    assert done == sorted(done) and progress[-1]['percent'] == 100
    assert all(p['percent'] < 100 for p in progress[:-1])
    assert progress[-1]['files_total'] == len(kokoro)


# ---- I-4 launcher port / log behaviour -------------------------------------
class BusySocket:
    def __init__(self, *a, **k):
        pass

    def setsockopt(self, *a):
        pass

    def bind(self, addr):
        raise OSError(98, 'Address already in use')

    def close(self):
        pass


class FreeSocket(BusySocket):
    def bind(self, addr):
        pass


def test_raw_occupied_port_gives_plain_error_and_quoted_log(tmp_path, no_sockets):
    env = {'T2A_LOG_DIR': str(tmp_path / 'My Logs'), 'T2A_PORT': '9123'}
    out = []
    code = lc.run_preflight(env=env, out=out.append, find_spec=lambda n: object(), platform='linux',
                            probe=lambda p: lc.port_free(p, socket_factory=BusySocket))
    text = '\n'.join(out)
    log = tmp_path / 'My Logs' / 'launch.log'
    assert code == 1 and '9123' in text and 'already in use' in text
    assert 'Errno' not in text and 'Traceback' not in text
    assert 'Log file: "%s"' % log in text
    assert 'Port 9123 is already in use' in log.read_text(encoding='utf-8')
    out = []
    code = lc.run_preflight(env=env, out=out.append, find_spec=lambda n: object(), platform='linux',
                            probe=lambda p: lc.port_free(p, socket_factory=FreeSocket))
    assert code == 0 and 'ready to start on port 9123' in '\n'.join(out)


def test_bind_race_record_goes_to_log_not_console(tmp_path):
    stream = io.StringIO()
    state = lc.setup_server_logging(env={'T2A_LOG_DIR': str(tmp_path / 'logs')}, platform='linux',
                                    stream=stream)
    try:
        logging.getLogger('uvicorn.error').error(OSError(98, 'error while attempting to bind'))
    finally:
        state.close()
    assert state.bind_error is True and state.written is True
    assert 'Errno' not in stream.getvalue()
    assert 'Errno 98' in Path(state.path).read_text(encoding='utf-8')


# ---- I-5 orchestration of I-1 + I-2 and models_cached -----------------------
def test_stage_models_selection_follows_saved_settings(tmp_path, monkeypatch):
    monkeypatch.delenv('T2A_DOWNLOAD_CHATTERBOX', raising=False)
    for free, expected in ((20480, True), (2048, False)):
        gpu = hardware.gpu_usable_from_settings(settings_file(tmp_path, free))
        seen = {}

        def fake(**kw):
            seen.update(kw)
            return {'reused': [], 'downloaded': []}
        assert ins.stage_models(ins.Reporter(lambda t: None), gpu, install=fake) is True
        assert seen['gpu_usable'] is expected and seen['include_chatterbox'] is expected


def test_verify_gate_combines_settings_install_and_models_cached(tmp_path, monkeypatch, no_sockets):
    kokoro, cb = patch_manifest(monkeypatch)
    root = tmp_path / 'hub'
    monkeypatch.setenv('HF_HUB_CACHE', str(root))
    monkeypatch.delenv('T2A_DEVICE', raising=False)
    monkeypatch.setattr(md, 'language_ready', lambda: True)
    monkeypatch.setattr(hardware, 'DEFAULT_SETTINGS_PATH', settings_file(tmp_path, 20480))
    do_install(root, Server({**kokoro, **cb}), include_chatterbox=True)
    # GPU settings say Chatterbox is needed; it is missing so the gate must fail.
    for name in engines.CHATTERBOX_FILES:
        os.remove(md.local_path(str(root), md.CHATTERBOX_REPO, name))
    rep = ins.Reporter(lambda t: None)
    assert ins.stage_verify(rep, tools=lambda: []) is False
    do_install(root, Server({**kokoro, **cb}), include_chatterbox=True)
    assert ins.stage_verify(ins.Reporter(lambda t: None), tools=lambda: []) is True
    # forced CPU: Chatterbox is not required for readiness
    for name in engines.CHATTERBOX_FILES:
        os.remove(md.local_path(str(root), md.CHATTERBOX_REPO, name))
    monkeypatch.setenv('T2A_DEVICE', 'cpu')
    assert ins.stage_verify(ins.Reporter(lambda t: None), tools=lambda: []) is True
    monkeypatch.setattr(md, 'language_ready', lambda: False)
    assert ins.stage_verify(ins.Reporter(lambda t: None), tools=lambda: []) is False


def test_full_15_voice_and_language_offline_readiness(tmp_path, monkeypatch, no_sockets):
    real = {s.rel for s in md.MANIFEST[md.KOKORO_REPO][1] if s.rel.startswith('voices/')}
    assert real == {'voices/%s.pt' % v for v in PRESET_VOICES} and len(real) == 15
    kokoro, _ = patch_manifest(monkeypatch, voices=tuple(PRESET_VOICES))
    root = tmp_path / 'hub'
    env = {'HF_HUB_CACHE': str(root)}
    monkeypatch.setattr(md, 'language_ready', lambda: True)
    assert off.models_cached(env) is False
    do_install(root, Server(kokoro))
    assert off.models_cached(env) is True
    assert all(off.voice_cached(v, env) for v in PRESET_VOICES)
    monkeypatch.setattr(md, 'language_ready', lambda: False)
    assert off.models_cached(env) is False
    monkeypatch.setattr(md, 'language_ready', lambda: True)
    os.remove(md.local_path(str(root), md.KOKORO_REPO, 'voices/bm_daniel.pt'))
    assert off.models_cached(env) is False
    assert off.configure_at_startup(dict(env)) == {}


def test_installer_output_is_what_the_runtime_resolves(tmp_path, monkeypatch, no_sockets):
    kokoro, cb = patch_manifest(monkeypatch)
    root = tmp_path / 'hub'
    monkeypatch.setenv('HF_HUB_CACHE', str(root))
    monkeypatch.setitem(sys.modules, 'huggingface_hub', None)  # any Hub import fails
    do_install(root, Server({**kokoro, **cb}), include_chatterbox=True)
    paths = md.kokoro_paths()
    assert os.path.isfile(paths['config']) and os.path.isfile(paths['model'])
    assert os.path.isfile(paths['voice']('af_heart'))
    snap = md.snapshot_dir(str(root), md.KOKORO_REPO)
    assert md.require_files(md.KOKORO_REPO, ['config.json', 'kokoro-v1_0.pth']) == snap
    seen = {}

    class FakeTTS:
        @classmethod
        def from_local(cls, ckpt_dir, device):
            seen['dir'] = ckpt_dir
            return types.SimpleNamespace(conds='c', sr=24000)

    monkeypatch.setattr(ce, '_chatterbox_tts', lambda: FakeTTS)
    assert isinstance(ce.load('cpu'), ce.ChatterboxEngine)
    assert seen['dir'] == Path(md.chatterbox_dir()) == Path(md.chatterbox_dir(str(root)))
    assert str(seen['dir']).endswith(engines.CHATTERBOX_REVISION)


# ---- import-light and API shape ------------------------------------------------
def test_hub_and_torch_not_imported_at_module_load():
    code = ('import sys; import backend.model_download, backend.offline, backend.device_fallback, '
            'backend.hardware, backend.launch_checks; '
            'bad=[m for m in ("huggingface_hub","transformers","torch","kokoro") if m in sys.modules]; '
            'assert not bad, bad')
    subprocess.run([sys.executable, '-c', code], cwd=str(ROOT), check=True)


@contextmanager
def isolated_server_module(tmp_path, monkeypatch):
    """Import the real API with owned paths and restore any previous module."""
    previous = sys.modules.get('server')
    namespace = dict(vars(previous)) if previous is not None else None
    with monkeypatch.context() as scoped:
        paths = {
            'HF_HOME': 'hf', 'HF_HUB_CACHE': 'hf/hub',
            'T2A_SETTINGS_PATH': 'settings.json', 'T2A_LIBRARY_DIR': 'library',
            'T2A_CACHE_DIR': 'cache', 'T2A_VOICES_DIR': 'voices',
            'T2A_PRON_PATH': 'pron.json', 'T2A_CONSENT_PATH': 'consent.json',
            'T2A_LOG_DIR': 'logs',
        }
        for key, relative in paths.items():
            scoped.setenv(key, str(tmp_path / relative))
        for key, value in {'T2A_DEVICE': 'cpu', 'T2A_PORT': '8765',
                           'T2A_CACHE_MAX_BYTES': '1000000', 'T2A_NO_BROWSER': '1',
                           'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}.items():
            scoped.setenv(key, value)
        try:
            module = importlib.import_module('server')
            if previous is not None:
                module = importlib.reload(module)
            yield module
        finally:
            if previous is None:
                sys.modules.pop('server', None)
            else:
                vars(previous).clear()
                vars(previous).update(namespace)
                sys.modules['server'] = previous


def test_api_voices_list_shape_unchanged(tmp_path, monkeypatch, no_sockets):
    with isolated_server_module(tmp_path, monkeypatch) as server:
        payload = server.voices_payload()
    assert payload[0]['id'] == 'studio_narrator' and payload[0]['kind'] == 'studio'
    assert [v['id'] for v in payload if v['kind'] == 'preset'] == list(PRESET_VOICES)
    for v in payload:
        assert {'id', 'label', 'accent', 'gender', 'kind', 'engine'} <= set(v)
    assert all(v['engine'] == 'kokoro' for v in payload if v['kind'] == 'preset')


def test_api_import_ignores_inherited_paths_and_restores_module(tmp_path, monkeypatch, no_sockets):
    inherited = tmp_path / 'inherited-host-surrogate'
    keys = ('HF_HOME', 'HF_HUB_CACHE', 'T2A_SETTINGS_PATH', 'T2A_LIBRARY_DIR',
            'T2A_CACHE_DIR', 'T2A_VOICES_DIR', 'T2A_PRON_PATH', 'T2A_CONSENT_PATH')
    for key in keys:
        monkeypatch.setenv(key, str(inherited / key))
    previous = sys.modules.get('server')
    saved = dict(vars(previous)) if previous is not None else None
    owned = tmp_path / 'owned'
    with isolated_server_module(owned, monkeypatch) as server:
        for name in ('LIBRARY_DIR', 'VOICES_DIR', 'PRON_PATH', 'CONSENT_PATH'):
            assert Path(getattr(server, name)).is_relative_to(owned)
        assert md.hub_cache() == str(owned / 'hf/hub')
        assert os.environ['T2A_CACHE_DIR'] == str(owned / 'cache')
        assert os.environ['T2A_SETTINGS_PATH'] == str(owned / 'settings.json')
        assert server.voices_payload()
    assert not inherited.exists()
    assert all(os.environ[key] == str(inherited / key) for key in keys)
    assert sys.modules.get('server') is previous
    if previous is not None:
        assert vars(previous).keys() == saved.keys()
        assert all(vars(previous)[key] is value for key, value in saved.items())
