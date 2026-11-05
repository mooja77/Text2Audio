'''Pre-launch checks and server log routing for Text2Audio (stdlib only, so they can run before FastAPI/soundfile).

This module lives in the backend package so it ships in the installed wheel as well as the
source checkout. scripts/launch_checks.py is a thin compatibility CLI for the BAT file.

Usage:  python scripts/launch_checks.py --check

The checks confirm the app is installed, that its port is free, and write a log to a
writable per-user location. The full quoted log path is always printed. Nothing is
started or opened by --check.
'''
import argparse
import datetime
import errno
import importlib.util
import json
import logging
import os
import socket
import sys
import tempfile
import time
import urllib.request

__all__ = ['HOST', 'DEFAULT_PORT', 'REQUIRED_PACKAGES', 'REQUIRED_MODULES', 'LOG_NAME', 'NOT_INSTALLED',
           'PORT_BUSY', 'BIND_FAILED', 'STARTUP_FAILED', 'BIND_ERRNOS', 'port_from_env',
           'missing_dependencies', 'port_free', 'log_dir_candidates', 'write_log', 'run_preflight',
           'report_bind_failure', 'report_startup_failure', 'bootstrap_or_exit', 'fetch_health',
           'wait_and_open', 'is_bind_error', 'setup_server_logging', 'ServerLogging', 'main']

HOST = '127.0.0.1'
DEFAULT_PORT = 8765
# (import names accepted, package name to tell the user). These are the packages server.py
# imports eagerly or needs for route registration (FastAPI File/Form needs python-multipart).
REQUIRED_PACKAGES = (
    (('fastapi',), 'fastapi'),
    (('uvicorn',), 'uvicorn'),
    (('soundfile',), 'soundfile'),
    (('numpy',), 'numpy'),
    (('num2words',), 'num2words'),
    (('python_multipart', 'multipart'), 'python-multipart'),
)
REQUIRED_MODULES = tuple(names[0] for names, _ in REQUIRED_PACKAGES)
LOG_NAME = 'launch.log'
BIND_ERRNOS = frozenset({errno.EADDRINUSE, 98, 48, 10048, 10013})
NOT_INSTALLED = ('Text2Audio is not installed yet (missing: {names}). Next step: double-click '
                 '"Install Text2Audio.bat", wait for the green "Done!" message, then start '
                 'Text2Audio again.')
PORT_BUSY = ('Port {port} is already in use, so Text2Audio cannot start. Text2Audio may already '
             'be running. Next step: close any other Text2Audio window (or the program using '
             'that port), then start Text2Audio again.')
BIND_FAILED = ('Text2Audio could not start on port {port}. Another program may have taken the '
               'port just now. Next step: close other Text2Audio windows and start it again.')
STARTUP_FAILED = ('Text2Audio stopped while starting on port {port}. Next step: close other '
                  'Text2Audio windows and start it again. If it keeps happening, give the log '
                  'file shown below to the person helping you.')


def port_from_env(env=None):
    env = os.environ if env is None else env
    raw = str(env.get('T2A_PORT', '')).strip()
    if raw.isdigit() and 1 <= int(raw) <= 65535:
        return int(raw)
    return DEFAULT_PORT


def _has(find_spec, name):
    try:
        return find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def missing_dependencies(find_spec=None):
    '''Package names (as pip knows them) that are not importable. Nothing is imported.'''
    find_spec = find_spec or importlib.util.find_spec
    return [package for names, package in REQUIRED_PACKAGES
            if not any(_has(find_spec, n) for n in names)]


def port_free(port, host=HOST, socket_factory=None):
    '''True if we can bind host:port right now. The socket is closed immediately.'''
    sock = None
    try:
        sock = (socket_factory or socket.socket)(socket.AF_INET, socket.SOCK_STREAM)
        if os.name != 'nt':
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def log_dir_candidates(env=None, platform=None):
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    home = env.get('USERPROFILE') or env.get('HOME') or os.path.expanduser('~')
    out = []
    if env.get('T2A_LOG_DIR'):
        out.append(env['T2A_LOG_DIR'])
    if platform.startswith('win'):
        base = env.get('LOCALAPPDATA') or os.path.join(home, 'AppData', 'Local')
    elif platform == 'darwin':
        base = os.path.join(home, 'Library', 'Logs')
    else:
        base = env.get('XDG_STATE_HOME') or os.path.join(home, '.local', 'state')
    out.append(os.path.join(base, 'Text2Audio', 'logs'))
    out.append(os.path.join(tempfile.gettempdir(), 'Text2Audio', 'logs'))
    return out


def write_log(lines, env=None, platform=None):
    '''Append lines to the first writable log location. Returns (path, written).'''
    candidates = log_dir_candidates(env, platform)
    stamp = datetime.datetime.now().isoformat(timespec='seconds')
    for folder in candidates:
        path = os.path.join(folder, LOG_NAME)
        try:
            os.makedirs(folder, exist_ok=True)
            with open(path, 'a', encoding='utf-8') as f:
                for line in lines:
                    f.write('%s %s\n' % (stamp, line))
            return path, True
        except OSError:
            continue
    return os.path.join(candidates[0], LOG_NAME), False


def _log_line(path, written):
    note = '' if written else ' (could not be written; please tell the person helping you)'
    return 'Log file: "%s"%s' % (path, note)


def run_preflight(port=None, env=None, out=print, probe=None, find_spec=None, platform=None):
    '''Run the checks, print plain-words results and the quoted log path. 0 = ready, 1 = not.'''
    env = os.environ if env is None else env
    port = port or port_from_env(env)
    probe = probe or port_free
    missing = missing_dependencies(find_spec)
    problems = []
    if missing:
        problems.append(NOT_INSTALLED.format(names=', '.join(missing)))
    elif not probe(port):
        problems.append(PORT_BUSY.format(port=port))
    path, written = write_log(['Launch check on port %d' % port] + (problems or ['All checks passed']),
                              env, platform)
    for problem in problems:
        out(problem)
    if not problems:
        out('Text2Audio is ready to start on port %d.' % port)
    out(_log_line(path, written))
    return 1 if problems else 0


def report_bind_failure(port, env=None, out=print, platform=None):
    '''The port was taken between the probe and the real bind.'''
    message = BIND_FAILED.format(port=port)
    path, written = write_log([message], env, platform)
    out(message)
    out(_log_line(path, written))


def report_startup_failure(port, env=None, out=print, platform=None):
    '''The server stopped for a reason that is not a busy port: never call it one.'''
    message = STARTUP_FAILED.format(port=port)
    path, written = write_log([message], env, platform)
    out(message)
    out(_log_line(path, written))


def bootstrap_or_exit(find_spec=None, env=None, out=print, exit_fn=sys.exit, platform=None):
    '''Run before FastAPI/soundfile are imported: a plain message instead of a traceback.'''
    missing = missing_dependencies(find_spec)
    if not missing:
        return
    message = NOT_INSTALLED.format(names=', '.join(missing))
    path, written = write_log([message], env, platform)
    out(message)
    out(_log_line(path, written))
    exit_fn(1)


# ---- server log routing ------------------------------------------------------
def is_bind_error(record):
    '''True for the ERROR record Uvicorn logs when it cannot bind its socket.'''
    if record.levelno < logging.ERROR:
        return False
    exc = record.msg if isinstance(record.msg, BaseException) else (
        record.exc_info[1] if record.exc_info else None)
    if isinstance(exc, OSError) and exc.errno in BIND_ERRNOS:
        return True
    try:
        return 'error while attempting to bind' in record.getMessage()
    except Exception:
        return False


class _BindWatch(logging.Handler):
    def __init__(self, state):
        super().__init__(logging.ERROR)
        self.state = state

    def emit(self, record):
        try:
            if is_bind_error(record):
                self.state.bind_error = True
        except Exception:
            pass


class _HideBind(logging.Filter):
    def filter(self, record):
        return not is_bind_error(record)


class ServerLogging:
    '''Handles installed on the uvicorn logger; close() puts the logger back.'''

    def __init__(self):
        self.path = None
        self.written = False
        self.bind_error = False
        self._handlers = []
        self._saved = None

    def close(self):
        logger = logging.getLogger('uvicorn')
        for handler in self._handlers:
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        self._handlers = []
        if self._saved is not None:
            logger.setLevel(self._saved[0])
            logger.propagate = self._saved[1]
            self._saved = None


def setup_server_logging(env=None, platform=None, stream=None):
    '''Send Uvicorn log records to the real launch log. The console gets the same records,
    except the raw bind error, which is only hidden when it really is in a writable log
    (the caller then prints one plain, actionable message instead).'''
    state = ServerLogging()
    logger = logging.getLogger('uvicorn')
    state._saved = (logger.level, logger.propagate)
    for folder in log_dir_candidates(env, platform):
        path = os.path.join(folder, LOG_NAME)
        try:
            os.makedirs(folder, exist_ok=True)
            handler = logging.FileHandler(path, encoding='utf-8')
        except OSError:
            continue
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s uvicorn: %(message)s'))
        state.path, state.written = path, True
        state._handlers.append(handler)
        break
    console = logging.StreamHandler(stream if stream is not None else sys.stderr)
    console.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    if state.written:
        console.addFilter(_HideBind())
    state._handlers += [_BindWatch(state), console]
    for handler in state._handlers:
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return state


def fetch_health(url, timeout=1.0):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=timeout) as response:
        return json.loads(response.read(65536).decode('utf-8'))


def wait_and_open(url, health_url, cancel, expected_pid, fetch=None, opener=None,
                  sleep=time.sleep, attempts=150, interval=0.2):
    '''Open the browser only once THIS process answers /api/health (so it really bound).

    Returns False without opening if cancelled (startup or bind failed) or on timeout.'''
    fetch = fetch or fetch_health
    for _ in range(attempts):
        if cancel.is_set():
            return False
        try:
            data = fetch(health_url)
        except Exception:
            data = None
        if isinstance(data, dict) and data.get('status') == 'ok' and data.get('pid') == expected_pid:
            if cancel.is_set():
                return False
            if opener is None:
                import webbrowser
                opener = webbrowser.open
            opener(url)
            return True
        sleep(interval)
    return False


def main(argv=None, **deps):
    parser = argparse.ArgumentParser(
        prog='launch_checks',
        description='Check that Text2Audio can start: it is installed, its port is free, and a '
                    'log file can be written. Nothing is started or opened.')
    parser.add_argument('--check', action='store_true',
                        help='run the checks and exit (0 = ready, 1 = not ready)')
    parser.parse_args(argv)
    return run_preflight(**deps)


if __name__ == '__main__':
    sys.exit(main())
