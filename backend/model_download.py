'''Pinned, resumable, verified model installer (stdlib transport, no Hub internals).

Kokoro (17 files) is always installed. Chatterbox (5 files) is installed only with a
usable GPU or T2A_DOWNLOAD_CHATTERBOX=1 and is never required for CPU readiness.
Every file is checked by exact size plus a streamed digest before it counts as ready.
Files live in a pinned snapshot dir (models--<repo>/snapshots/<revision>/) that the
runtime loads from by local path, so installer and runtime share one cache.
huggingface_hub is never imported here.

Model-file completeness (kokoro_ready/repo_ready) is separate from full offline
readiness (models_ready, which also needs the spaCy language model installed later).
'''
import errno
import hashlib
import http.client
import importlib.metadata
import json
import os
import shutil
import time
import urllib.error
import urllib.request
from collections import namedtuple

from pipeline.engines import CHATTERBOX_FILES, CHATTERBOX_REPO, CHATTERBOX_REVISION

try:
    import msvcrt
except ImportError:
    msvcrt = None
try:
    import fcntl
except ImportError:
    fcntl = None

Spec = namedtuple('Spec', 'rel size digest kind', defaults=('sha256',))
KOKORO_REPO = 'hexgrad/Kokoro-82M'
KOKORO_REV = 'f3ff3571791e39611d31c381e3a41a3af07b4987'
LANGUAGE_VERSION = '3.8.0'
CHUNK = 1 << 20
MB = 1024 * 1024
MARGIN_MIN = 64 * MB
LOCK_NAME = '.t2a-install.lock'
CHECKPOINT = '.t2a-checkpoint.json'


def _specs(text, prefix='', suffix=''):
    out = []
    for line in text.strip().splitlines():
        name, size, digest, *git = line.split()
        out.append(Spec(prefix + name + suffix, int(size), digest, 'git' if git else 'sha256'))
    return tuple(out)


_KOKORO = _specs('''
config.json 2351 14a726edd3718279eac426630879ff743955b16a g
kokoro-v1_0.pth 327212226 496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4
''')
_VOICES = _specs('''
af_heart 523425 0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff
af_bella 523425 8cb64e02fcc8de0327a8e13817e49c76c945ecf0052ceac97d3081480e8e48d6
af_nicole 523430 c5561808bcf5250fe8c5f5de32caf2d94f27e57e95befdb098c5c85991d4c5da
af_sarah 523425 49bd364ea3be9eb3e9685e8f9a15448c4883112a7c0ff7ab139fa4088b08cef9
af_sky 523351 c799548aed06e0cb0d655a85a01b48e7f10484d71663f9a3045a5b9362e8512c
am_michael 523435 9a443b79a4b22489a5b0ab7c651a0bcd1a30bef675c28333f06971abbd47bd37
am_adam 523420 ced7e284aba12472891be1da3ab34db84cc05cc02b5889535796dbf2d8b0cb34
am_echo 523420 8bcfdc852bc985fb45c396c561e571ffb9183930071f962f1b50df5c97b161e8
am_liam 523420 c82550757ddb31308b97f30040dda8c2d609a9e2de6135848d0a948368138518
bf_emma 523420 d0a423deabf4a52b4f49318c51742c54e21bb89bbbe9a12141e7758ddb5da701
bf_isabella 523440 cdd4c37003805104d1d08fb1e05855c8fb2c68de24ca6e71f264a30aaa59eefd
bf_alice 523425 d292651b6af6c0d81705c2580dcb4463fccc0ff7b8d618a471dbb4e45655b3f3
bm_george 523430 f1bc812213dc59774769e5c80004b13eeb79bd78130b11b2d7f934542dab811b
bm_lewis 523425 b5204750dcba01029d2ac9cec17aec3b20a6d64073c579d694a23cb40effbd0e
bm_daniel 523430 fc3fce4e9c12ed4dbc8fa9680cfe51ee190a96444ce7c3ad647549a30823fc5d
''', 'voices/', '.pt')
_CHATTERBOX = _specs('''
ve.safetensors 5695784 f0921cab452fa278bc25cd23ffd59d36f816d7dc5181dd1bef9751a7fb61f63c
t3_cfg.safetensors 2129653744 914cb1696f47527fe8852ca8f1fe1fa63cb34f76f9c715e84e067b744dd0da81
s3gen.safetensors 1056484620 2b78103c654207393955e4900aac14a12de8ef25f4b09424f1ef91941f161d4e
tokenizer.json 25470 abd07c710243ba89bf1b21780e7c37ddde92334e g
conds.pt 107374 6552d70568833628ba019c6b03459e77fe71ca197d5c560cef9411bee9d87f4e
''')

MANIFEST = {KOKORO_REPO: (KOKORO_REV, _KOKORO + _VOICES),
            CHATTERBOX_REPO: (CHATTERBOX_REVISION, _CHATTERBOX)}


class DiskSpaceError(RuntimeError):
    pass


class DownloadError(RuntimeError):
    pass


class InstallBusy(RuntimeError):
    pass


class CorruptDownload(Exception):
    pass


# ---- paths, selection, runtime bridge -------------------------------------
def hub_cache(env=None):
    env = os.environ if env is None else env
    if env.get('HF_HUB_CACHE'):
        return env['HF_HUB_CACHE']
    home = env.get('HF_HOME') or os.path.join(os.path.expanduser('~'), '.cache', 'huggingface')
    return os.path.join(home, 'hub')


def _repo_dir(root, repo):
    return os.path.join(root, 'models--' + repo.replace('/', '--'))


def snapshot_dir(root, repo):
    return os.path.join(_repo_dir(root, repo), 'snapshots', MANIFEST[repo][0])


def local_path(root, repo, rel):
    return os.path.join(snapshot_dir(root, repo), *rel.split('/'))


def kokoro_paths(root=None):
    '''Local paths for KModel(config=, model=) and KPipeline voices (no Hub lookups).'''
    root = root or hub_cache()
    return {'config': local_path(root, KOKORO_REPO, 'config.json'),
            'model': local_path(root, KOKORO_REPO, 'kokoro-v1_0.pth'), 'repo_id': KOKORO_REPO,
            'voice': lambda name: local_path(root, KOKORO_REPO, 'voices/%s.pt' % name)}


def chatterbox_dir(root=None):
    return snapshot_dir(root or hub_cache(), CHATTERBOX_REPO)


def want_chatterbox(env=None, gpu_usable=False):
    env = os.environ if env is None else env
    return env.get('T2A_DOWNLOAD_CHATTERBOX') == '1' or bool(gpu_usable)


# ---- verification and readiness -------------------------------------------
def digest_of(path, kind):
    h = hashlib.sha1() if kind == 'git' else hashlib.sha256()
    if kind == 'git':
        h.update(b'blob %d' % os.path.getsize(path) + bytes(1))
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(CHUNK), b''):
            h.update(block)
    return h.hexdigest()


def is_valid(path, spec):
    '''Exact size, then streamed digest. Nothing is trusted from a checkpoint.'''
    try:
        return os.path.getsize(path) == spec.size and digest_of(path, spec.kind) == spec.digest
    except OSError:
        return False


def repo_ready(root, repo):
    return all(is_valid(local_path(root, repo, s.rel), s) for s in MANIFEST[repo][1])


def kokoro_ready(root=None):
    return repo_ready(root or hub_cache(), KOKORO_REPO)


def language_ready():
    try:
        return importlib.metadata.version('en_core_web_sm') == LANGUAGE_VERSION
    except importlib.metadata.PackageNotFoundError:
        return False


def models_ready(root=None, env=None, gpu_usable=False):
    '''Full offline readiness: Kokoro files + language model; Chatterbox only if wanted.'''
    env = os.environ if env is None else env
    root = root or hub_cache(env)
    need = [KOKORO_REPO] + ([CHATTERBOX_REPO] if want_chatterbox(env, gpu_usable) else [])
    return language_ready() and all(repo_ready(root, r) for r in need)


def write_checkpoint(root, verified):
    '''Advisory only (never skips verification). Atomic replace.'''
    path = os.path.join(root, CHECKPOINT)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'verified': verified, 'time': int(time.time())}, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_checkpoint(root):
    try:
        with open(os.path.join(root, CHECKPOINT), encoding='utf-8') as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


# ---- owner-safe OS lock (released on process exit; never unlinked) ---------
class InstallLock:
    def __init__(self, path):
        self.path, self.f = path, None

    def __enter__(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        f = open(self.path, 'a+b')
        try:
            if msvcrt:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            raise InstallBusy('Another Text2Audio model download is already running. '
                              'Wait for it to finish, then try again.') from None
        self.f = f
        return self

    def __exit__(self, *exc):
        f, self.f = self.f, None
        try:
            if msvcrt:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        finally:
            f.close()


# ---- disk check ------------------------------------------------------------
def check_disk(root, missing, disk_usage=shutil.disk_usage):
    '''Exact bytes still missing, plus a labelled estimated margin, on the cache filesystem.'''
    if missing <= 0:
        return
    probe = os.path.abspath(root)
    while not os.path.exists(probe) and os.path.dirname(probe) != probe:
        probe = os.path.dirname(probe)
    free = disk_usage(probe).free
    margin = max(MARGIN_MIN, missing // 50)
    if free < missing + margin:
        raise DiskSpaceError(
            'Not enough free disk space for the voice models. Still to download: '
            '{:,} bytes ({:.1f} MB, exact). Estimated safety margin: {:.0f} MB (an estimate). '
            'Free space: {:.1f} MB. Free up space and run the download again; finished files '
            'are kept.'.format(missing, missing / MB, margin / MB, free / MB))


# ---- progress --------------------------------------------------------------
class Tracker:
    '''Aggregate byte progress: monotonic high-water mark, 99 max until all verified.'''

    def __init__(self, total, files_total, cb):
        self.total, self.files_total, self.cb = max(1, total), files_total, cb
        self.base = self.cur = self.hw = self.done = self.fsize = 0
        self.name = ''

    def start(self, name, size, offset):
        self.name, self.fsize, self.cur = name, size, offset
        self.emit()

    def update(self, cur):
        self.cur = cur
        self.emit()

    def finish_file(self):
        self.base += self.fsize
        self.cur, self.done = 0, self.done + 1
        self.emit()

    def emit(self, final=False):
        self.hw = max(self.hw, self.base + self.cur)
        if final:
            self.hw = self.total
        if self.cb is None:
            return
        self.cb({'file': self.name, 'file_bytes': self.cur, 'file_total': self.fsize,
                 'file_mb': self.cur / MB, 'file_total_mb': self.fsize / MB,
                 'done_bytes': self.hw, 'total_bytes': self.total,
                 'done_mb': self.hw / MB, 'total_mb': self.total / MB,
                 'percent': 100 if final else min(99, self.hw * 100 // self.total),
                 'files_done': self.done, 'files_total': self.files_total})


# ---- transport: persistent partial file + HTTP Range/validator resume ------
def urllib_opener(url, headers):
    req = urllib.request.Request(url, headers=dict(headers, **{'User-Agent': 'text2audio-model-download'}))
    return urllib.request.urlopen(req, timeout=60)


def _url(repo, rev, rel):
    return 'https://huggingface.co/%s/resolve/%s/%s' % (repo, rev, rel)


def _part_paths(root, repo, rel):
    base = os.path.join(_repo_dir(root, repo), 'partial', rel.replace('/', '__'))
    return base + '.part', base + '.part.json'


def _discard(*paths):
    for p in paths:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass


def _resume_offset(part, meta, spec):
    try:
        with open(meta, encoding='utf-8') as f:
            m = json.load(f)
        n = os.path.getsize(part)
    except (OSError, ValueError):
        return 0, None
    if m.get('size') != spec.size or m.get('digest') != spec.digest or not 0 <= n <= spec.size:
        return 0, None
    return n, m.get('etag')


def _accept(resp, offset, spec, meta):
    '''Check the reply; return the offset to write from (0 means restart).'''
    status, h = getattr(resp, 'status', 200), resp.headers
    if status == 206 and offset:
        cr = h.get('Content-Range') or ''
        try:
            a, b = cr.removeprefix('bytes ').split('/')[0].split('-')
            total = int(cr.split('/')[1])
            ok = cr.startswith('bytes ') and (int(a), int(b), total) == (offset, spec.size - 1, spec.size)
        except (ValueError, IndexError):
            ok = False
        if not ok:
            raise CorruptDownload('unexpected Content-Range: ' + cr)
    elif status == 200:
        length = h.get('Content-Length')
        if length is not None and int(length) != spec.size:
            raise CorruptDownload('unexpected Content-Length')
        offset = 0  # server ignored Range or validator changed: restart cleanly
    else:
        raise ConnectionError('unexpected HTTP status %s' % status)
    with open(meta, 'w', encoding='utf-8') as f:
        json.dump({'size': spec.size, 'digest': spec.digest, 'etag': h.get('ETag')}, f)
    return offset


def _fetch(repo, rev, spec, root, final, opener, tracker):
    part, meta = _part_paths(root, repo, spec.rel)
    os.makedirs(os.path.dirname(part), exist_ok=True)
    os.makedirs(os.path.dirname(final), exist_ok=True)
    offset, etag = _resume_offset(part, meta, spec)
    if offset == 0:
        _discard(part, meta)
    tracker.start(spec.rel, spec.size, offset)
    if offset < spec.size:
        headers = {}
        if offset:
            headers['Range'] = 'bytes=%d-' % offset
            if etag:
                headers['If-Range'] = etag
        resp = opener(_url(repo, rev, spec.rel), headers)
        try:
            offset = _accept(resp, offset, spec, meta)
            tracker.update(offset)
            with open(part, 'ab' if offset else 'wb') as f:
                for block in iter(lambda: resp.read(CHUNK), b''):
                    f.write(block)
                    offset += len(block)
                    if offset > spec.size:
                        raise CorruptDownload('server sent too many bytes')
                    tracker.update(offset)
        finally:
            resp.close()
    if os.path.getsize(part) != spec.size:
        raise ConnectionError('download ended early')
    if not is_valid(part, spec):
        raise CorruptDownload('digest mismatch for ' + spec.rel)
    os.replace(part, final)
    _discard(meta)
    tracker.finish_file()


def _download(repo, rev, spec, root, final, opener, tracker, retries, sleep):
    last = None
    for attempt in range(retries + 1):
        part, meta = _part_paths(root, repo, spec.rel)
        try:
            return _fetch(repo, rev, spec, root, final, opener, tracker)
        except urllib.error.HTTPError as exc:
            if exc.code == 416:
                _discard(part, meta)
            elif exc.code < 500 and exc.code != 429:
                raise DownloadError('The model server refused %s (HTTP %d).' % (spec.rel, exc.code)) from exc
            last = exc
        except CorruptDownload as exc:
            _discard(part, meta)
            last = exc
        except (OSError, http.client.HTTPException) as exc:
            if getattr(exc, 'errno', None) == errno.ENOSPC:
                raise DiskSpaceError('The disk filled up while downloading %s. Free up space and '
                                     'run the download again; finished files are kept.' % spec.rel) from exc
            last = exc
        if attempt < retries:
            sleep(min(2 ** attempt, 30))
    raise DownloadError('Could not download %s after %d attempts (%s). Check your internet '
                        'connection and run the download again.' % (spec.rel, retries + 1, last))


# ---- installer -------------------------------------------------------------
def install(env=None, *, include_chatterbox=None, gpu_usable=False, root=None, opener=None,
            progress=None, sleep=time.sleep, disk_usage=shutil.disk_usage, retries=3):
    '''Download/repair the selected pinned files. Succeeds once the files verify;
    the language model (installed separately) is not checked here.'''
    env = os.environ if env is None else env
    root = root or hub_cache(env)
    if include_chatterbox is None:
        include_chatterbox = want_chatterbox(env, gpu_usable)
    repos = [KOKORO_REPO] + ([CHATTERBOX_REPO] if include_chatterbox else [])
    opener = opener or urllib_opener
    plan = [(r, MANIFEST[r][0], s) for r in repos for s in MANIFEST[r][1]]
    os.makedirs(root, exist_ok=True)
    with InstallLock(os.path.join(root, LOCK_NAME)):
        reused, repaired, pending, missing = [], [], [], 0
        for repo, rev, s in plan:
            final = local_path(root, repo, s.rel)
            if os.path.exists(final):
                if is_valid(final, s):
                    reused.append(s)
                    continue
                os.remove(final)  # same-size or truncated corruption: repair
                repaired.append(s.rel)
            pending.append((repo, rev, s, final))
            missing += s.size - _resume_offset(*_part_paths(root, repo, s.rel), s)[0]
        check_disk(root, missing, disk_usage)
        tracker = Tracker(sum(s.size for _, _, s in plan), len(plan), progress)
        tracker.base, tracker.done = sum(s.size for s in reused), len(reused)
        tracker.emit()
        for repo, rev, s, final in pending:
            _download(repo, rev, s, root, final, opener, tracker, retries, sleep)
        write_checkpoint(root, {r: {s.rel: s.size for s in MANIFEST[r][1]} for r in repos})
        tracker.emit(final=True)
    return {'repos': repos, 'reused': [s.rel for s in reused], 'repaired': repaired,
            'downloaded': [s.rel for _, _, s, _ in pending]}


def main(argv=None):
    from backend import hardware
    gpu = hardware.gpu_usable_from_settings(hardware.DEFAULT_SETTINGS_PATH)

    def show(p):
        print('%3d%% %s %.1f/%.1f MB (total %.0f/%.0f MB)' % (
            p['percent'], p['file'], p['file_mb'], p['file_total_mb'], p['done_mb'], p['total_mb']),
            end=chr(13), flush=True)
    try:
        install(include_chatterbox=want_chatterbox(os.environ, gpu), progress=show)
    except (DiskSpaceError, DownloadError, InstallBusy) as exc:
        print()
        print(exc)
        return 1
    print()
    print('Model files verified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
