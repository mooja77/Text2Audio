'''Pre-launch checks for Text2Audio (stdlib only, so they can run before FastAPI/soundfile).

Usage:  python scripts/launch_checks.py --check

The checks confirm the app is installed, that its port is free, and write a log to a
writable per-user location. The full quoted log path is always printed. Nothing is
started or opened by --check.
'''
import argparse
import datetime
import importlib.util
import json
import os
import socket
import sys
import tempfile
import time
import urllib.request

HOST = '127.0.0.1'
DEFAULT_PORT = 8765
REQUIRED_MODULES = ('fastapi', 'uvicorn', 'soundfile', 'numpy')
LOG_NAME = 'launch.log'
NOT_INSTALLED = ('Text2Audio is not installed yet (missing: {names}). Next step: double-click '
                 '"Install Text2Audio.bat", wait for the green "Done!" message, then start '
                 'Text2Audio again.')
PORT_BUSY = ('Port {port} is already in use, so Text2Audio cannot start. Text2Audio may already '
             'be running. Next step: close any other Text2Audio window (or the program using '
             'that port), then start Text2Audio again.')
BIND_FAILED = ('Text2Audio could not start on port {port}. Another program may have taken the '
               'port just now. Next step: close other Text2Audio windows and start it again.')


def port_from_env(env=None):
    env = os.environ if env is None else env
    raw = str(env.get('T2A_PORT', '')).strip()
    if raw.isdigit() and 1 <= int(raw) <= 65535:
        return int(raw)
    return DEFAULT_PORT


def missing_dependencies(find_spec=None):
    find_spec = find_spec or importlib.util.find_spec
    missing = []
    for name in REQUIRED_MODULES:
        try:
            found = find_spec(name) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append(name)
    return missing


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
