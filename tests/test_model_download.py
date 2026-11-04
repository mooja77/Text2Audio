'''Mocked tests for backend.model_download: no network, no GPU, no Hub.'''
import errno
import hashlib
import importlib.metadata
import json
import os
import types

import pytest

from backend import model_download as md
from pipeline.engines import CHATTERBOX_FILES

DATA = {'config.json': b'{"a": 1}', 'm.bin': bytes(range(256)) * 12}
CB = {'c.bin': bytes(reversed(range(256))) * 5}
BIG = lambda p: types.SimpleNamespace(free=10 ** 12)
NOSLEEP = lambda s: None


def spec(rel, data, kind='sha256'):
    if kind == 'git':
        d = hashlib.sha1(b'blob %d' % len(data) + bytes(1) + data).hexdigest()
    else:
        d = hashlib.sha256(data).hexdigest()
    return md.Spec(rel, len(data), d, kind)


class Resp:
    def __init__(self, status, headers, body, cut, srv):
        self.status, self.headers, self.body, self.cut, self.srv, self.pos = status, headers, body, cut, srv, 0

    def read(self, n):
        end = min(len(self.body), self.pos + n)
        if self.cut is not None:
            if self.pos >= self.cut:
                raise ConnectionResetError('reset')
            end = min(end, self.cut)
        chunk = self.body[self.pos:end]
        self.pos = end
        self.srv.served += len(chunk)
        return chunk

    def close(self):
        pass


class Server:
    def __init__(self, files, honor_range=True, bad_range=False, cut=None):
        self.files, self.honor, self.bad, self.cut = files, honor_range, bad_range, dict(cut or {})
        self.calls, self.served = [], 0

    def __call__(self, url, headers):
        self.calls.append((url, dict(headers)))
        name = url.split('/resolve/', 1)[1].split('/', 1)[1]
        data, start, status = self.files[name], 0, 200
        if headers.get('Range') and self.honor:
            start, status = int(headers['Range'].split('=')[1].rstrip('-')), 206
        hdr = {'ETag': 'e-' + name, 'Content-Length': str(len(data) - start)}
        if status == 206:
            hdr['Content-Range'] = 'bytes %d-%d/%d' % (start + (1 if self.bad else 0), len(data) - 1, len(data))
        return Resp(status, hdr, data[start:], self.cut.pop(name, None), self)

    def names(self):
        return [c[0].rsplit('/', 1)[1] for c in self.calls]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    k = (spec('config.json', DATA['config.json'], 'git'), spec('m.bin', DATA['m.bin']))
    monkeypatch.setattr(md, 'MANIFEST', {md.KOKORO_REPO: (md.KOKORO_REV, k),
                                         md.CHATTERBOX_REPO: ('r' * 40, (spec('c.bin', CB['c.bin']),))})
    monkeypatch.setattr(md, 'CHUNK', 1000)
    return str(tmp_path), k


def run(root, srv, **kw):
    return md.install(root=root, opener=srv, sleep=NOSLEEP, disk_usage=BIG, **kw)


def seed(root, s, n):
    part, meta = md._part_paths(root, md.KOKORO_REPO, s.rel)
    os.makedirs(os.path.dirname(part), exist_ok=True)
    with open(part, 'wb') as f:
        f.write(DATA[s.rel][:n])
    with open(meta, 'w') as f:
        json.dump({'size': s.size, 'digest': s.digest, 'etag': 'e-' + s.rel}, f)


def test_manifest_has_pinned_17_plus_5_files():
    rev, k = md.MANIFEST[md.KOKORO_REPO]
    assert rev == 'f3ff3571791e39611d31c381e3a41a3af07b4987' and len(k) == 17
    voices = [s.rel for s in k if s.rel.startswith('voices/')]
    assert len(voices) == 15 and 'voices/bm_daniel.pt' in voices
    assert {s.rel: s.size for s in k}['kokoro-v1_0.pth'] == 327212226
    cb = md.MANIFEST[md.CHATTERBOX_REPO][1]
    assert {s.rel for s in cb} == set(CHATTERBOX_FILES) and len(cb) == 5
    for s in k + cb:
        assert len(s.digest) == (40 if s.kind == 'git' else 64) and int(s.digest, 16) >= 0
    assert [s.rel for s in k + cb if s.kind == 'git'] == ['config.json', 'tokenizer.json']


def test_chatterbox_selection_gpu_or_opt_in_only():
    assert not md.want_chatterbox({}, False)
    assert md.want_chatterbox({}, True)
    assert md.want_chatterbox({'T2A_DOWNLOAD_CHATTERBOX': '1'}, False)
    assert not md.want_chatterbox({'T2A_DOWNLOAD_CHATTERBOX': '0'}, False)


def test_install_progress_is_monotonic_and_below_100_until_verified(env):
    root, _ = env
    seen = []
    md.install(root=root, opener=Server(DATA), progress=seen.append, sleep=NOSLEEP, disk_usage=BIG)
    done = [p['done_bytes'] for p in seen]
    assert done == sorted(done) and seen[-1]['percent'] == 100
    assert all(p['percent'] < 100 for p in seen[:-1])
    assert {'file', 'file_mb', 'file_total_mb', 'done_mb', 'total_mb'} <= seen[0].keys()
    assert md.kokoro_ready(root)


def test_interrupted_transfer_resumes_with_range_and_validator(env):
    root, _ = env
    srv, seen = Server(DATA, cut={'m.bin': 1500}), []
    md.install(root=root, opener=srv, progress=seen.append, sleep=NOSLEEP, disk_usage=BIG)
    calls = [c for c in srv.calls if c[0].endswith('m.bin')]
    assert len(calls) == 2 and 'Range' not in calls[0][1]
    assert calls[1][1] == {'Range': 'bytes=1500-', 'If-Range': 'e-m.bin'}
    assert srv.served == sum(len(v) for v in DATA.values())  # no re-download of kept bytes
    done = [p['done_bytes'] for p in seen]
    assert done == sorted(done) and done[-1] == seen[-1]['total_bytes']
    assert md.kokoro_ready(root)


def test_persisted_partial_resumes_across_runs(env):
    root, k = env
    seed(root, k[1], 1200)
    srv = Server(DATA)
    run(root, srv)
    assert srv.calls[-1][1]['Range'] == 'bytes=1200-'
    assert md.kokoro_ready(root)


def test_server_ignoring_range_restarts_cleanly(env):
    root, k = env
    seed(root, k[1], 1200)
    run(root, Server(DATA, honor_range=False))
    assert md.kokoro_ready(root)


def test_bad_content_range_restarts_from_zero(env):
    root, k = env
    seed(root, k[1], 1200)
    srv = Server(DATA, bad_range=True)
    run(root, srv)
    calls = [c for c in srv.calls if c[0].endswith('m.bin')]
    assert 'Range' in calls[0][1] and 'Range' not in calls[1][1]
    assert md.kokoro_ready(root)


def test_same_size_corruption_is_repaired_and_valid_files_kept(env):
    root, k = env
    run(root, Server(DATA))
    final = md.local_path(root, md.KOKORO_REPO, 'm.bin')
    bad = bytearray(DATA['m.bin'])
    bad[0] ^= 1
    with open(final, 'wb') as f:
        f.write(bad)
    assert not md.kokoro_ready(root)
    srv = Server(DATA)
    rep = run(root, srv)
    assert srv.names() == ['m.bin'] and rep['repaired'] == ['m.bin'] and rep['reused'] == ['config.json']
    assert md.kokoro_ready(root)


def test_persistent_digest_mismatch_fails_without_final_file(env):
    root, _ = env
    bad = {'config.json': DATA['config.json'], 'm.bin': bytes(reversed(DATA['m.bin']))}
    with pytest.raises(md.DownloadError):
        run(root, Server(bad), retries=1)
    assert not os.path.exists(md.local_path(root, md.KOKORO_REPO, 'm.bin'))
    assert not os.path.exists(md._part_paths(root, md.KOKORO_REPO, 'm.bin')[0])


def test_disk_check_reports_exact_missing_bytes_and_labelled_margin(env):
    root, k = env
    srv = Server(DATA)
    with pytest.raises(md.DiskSpaceError) as exc:
        md.install(root=root, opener=srv, sleep=NOSLEEP,
                   disk_usage=lambda p: types.SimpleNamespace(free=100))
    total = sum(s.size for s in k)
    assert '{:,}'.format(total) in str(exc.value) and 'estimated' in str(exc.value).lower()
    assert srv.calls == []


def test_enospc_during_transfer_is_friendly(env):
    root, _ = env

    def full(url, headers):
        raise OSError(errno.ENOSPC, 'No space left on device')
    with pytest.raises(md.DiskSpaceError, match='disk filled up'):
        run(root, full)


def test_lock_is_exclusive_and_never_unlinked(tmp_path):
    p = str(tmp_path / 'x.lock')
    with md.InstallLock(p):
        with pytest.raises(md.InstallBusy):
            md.InstallLock(p).__enter__()
    assert os.path.exists(p)
    with md.InstallLock(p):
        pass


def test_readiness_is_conditional_and_separate_from_files(env, monkeypatch):
    root, _ = env
    run(root, Server(DATA))
    monkeypatch.setattr(md, 'language_ready', lambda: False)
    assert md.kokoro_ready(root) and not md.models_ready(root, env={})
    monkeypatch.setattr(md, 'language_ready', lambda: True)
    assert md.models_ready(root, env={}, gpu_usable=False)  # CPU: Chatterbox not required
    assert not md.models_ready(root, env={}, gpu_usable=True)
    assert not md.models_ready(root, env={'T2A_DOWNLOAD_CHATTERBOX': '1'})
    run(root, Server({**DATA, **CB}), include_chatterbox=True)
    assert md.models_ready(root, env={}, gpu_usable=True)


def test_checkpoint_is_advisory_atomic_and_reverified(env):
    root, _ = env
    run(root, Server(DATA))
    assert md.read_checkpoint(root)['verified'][md.KOKORO_REPO]['m.bin'] == len(DATA['m.bin'])
    assert not os.path.exists(os.path.join(root, md.CHECKPOINT + '.tmp'))
    final = md.local_path(root, md.KOKORO_REPO, 'm.bin')
    with open(final, 'r+b') as f:
        f.write(b'\xff')
    assert not md.kokoro_ready(root)


def test_language_model_version_is_required(monkeypatch):
    monkeypatch.setattr(importlib.metadata, 'version', lambda n: '3.8.0')
    assert md.language_ready()
    monkeypatch.setattr(importlib.metadata, 'version', lambda n: '3.7.1')
    assert not md.language_ready()

    def missing(n):
        raise importlib.metadata.PackageNotFoundError(n)
    monkeypatch.setattr(importlib.metadata, 'version', missing)
    assert not md.language_ready()


def test_runtime_bridge_uses_pinned_local_paths(tmp_path):
    paths = md.kokoro_paths(str(tmp_path))
    snap = os.path.join(str(tmp_path), 'models--hexgrad--Kokoro-82M', 'snapshots', md.KOKORO_REV)
    assert paths['config'] == os.path.join(snap, 'config.json')
    assert paths['model'] == os.path.join(snap, 'kokoro-v1_0.pth')
    assert paths['voice']('af_heart') == os.path.join(snap, 'voices', 'af_heart.pt')
    assert md.chatterbox_dir(str(tmp_path)).endswith(os.path.join('snapshots', md.CHATTERBOX_REVISION_FOR_TEST)) \
        if hasattr(md, 'CHATTERBOX_REVISION_FOR_TEST') else md.chatterbox_dir(str(tmp_path)).endswith(md.CHATTERBOX_REVISION)
