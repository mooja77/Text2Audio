import os
import socket
import threading
import time
import webbrowser

import pytest

from scripts import launch_checks as lc


class BusySocket:
    def __init__(self, *a, **k):
        self.closed = False

    def setsockopt(self, *a):
        pass

    def bind(self, addr):
        raise OSError(98, 'Address already in use')

    def close(self):
        self.closed = True


class FreeSocket(BusySocket):
    def bind(self, addr):
        self.addr = addr


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def deny(*a, **k):
        raise AssertionError('real socket/browser used')
    monkeypatch.setattr(socket, 'socket', deny)
    monkeypatch.setattr(socket, 'create_connection', deny)
    monkeypatch.setattr(webbrowser, 'open', deny)


def win_env(tmp_path):
    return {'LOCALAPPDATA': str(tmp_path / 'Jo Smith' / 'AppData' / 'Local')}


def ok_spec(name):
    return object()


def test_port_free_uses_injected_socket():
    assert lc.port_free(8765, socket_factory=FreeSocket) is True
    assert lc.port_free(8765, socket_factory=BusySocket) is False


def test_port_from_env():
    assert lc.port_from_env({}) == 8765
    assert lc.port_from_env({'T2A_PORT': '9001'}) == 9001
    assert lc.port_from_env({'T2A_PORT': 'abc'}) == 8765
    assert lc.port_from_env({'T2A_PORT': '70000'}) == 8765


def test_busy_port_gives_plain_message_and_nonzero(tmp_path):
    out = []
    code = lc.run_preflight(port=8765, env=win_env(tmp_path), out=out.append,
                            probe=lambda p: False, find_spec=ok_spec, platform='win32')
    text = '\n'.join(out)
    assert code == 1
    assert '8765' in text and 'already in use' in text and 'Next step' in text
    assert 'Errno' not in text and 'Traceback' not in text


def test_log_path_with_spaces_is_quoted_and_written(tmp_path):
    env = win_env(tmp_path)
    out = []
    code = lc.run_preflight(port=8765, env=env, out=out.append, probe=lambda p: True,
                            find_spec=ok_spec, platform='win32')
    expected = os.path.join(env['LOCALAPPDATA'], 'Text2Audio', 'logs', 'launch.log')
    assert code == 0
    assert 'Log file: "%s"' % expected in '\n'.join(out)
    assert os.path.isfile(expected)


def test_unwritable_log_dir_falls_back(tmp_path):
    blocker = tmp_path / 'blocker'
    blocker.write_text('x')
    env = dict(win_env(tmp_path), T2A_LOG_DIR=str(blocker / 'sub'))
    path, written = lc.write_log(['hello'], env, 'win32')
    assert written and path.startswith(env['LOCALAPPDATA'])


def test_missing_dependencies_say_install(tmp_path):
    out = []
    code = lc.run_preflight(port=8765, env=win_env(tmp_path), out=out.append,
                            probe=lambda p: True, find_spec=lambda n: None, platform='win32')
    assert code == 1 and 'Install Text2Audio.bat' in '\n'.join(out)


def test_help_exits_zero_without_socket_or_browser(capsys):
    with pytest.raises(SystemExit) as exc:
        lc.main(['--help'])
    assert exc.value.code == 0
    assert '--check' in capsys.readouterr().out


def test_check_cli_uses_injected_probe(tmp_path, capsys):
    deps = dict(env=win_env(tmp_path), find_spec=ok_spec, platform='win32')
    assert lc.main(['--check'], probe=lambda p: True, **deps) == 0
    assert lc.main(['--check'], probe=lambda p: False, **deps) == 1
    assert 'Log file: "' in capsys.readouterr().out


def test_bootstrap_exits_before_imports_when_missing(tmp_path):
    out, codes = [], []
    lc.bootstrap_or_exit(find_spec=lambda n: None, env=win_env(tmp_path), out=out.append,
                         exit_fn=codes.append, platform='win32')
    assert codes == [1] and 'not installed' in out[0] and 'Log file: "' in out[1]
    lc.bootstrap_or_exit(find_spec=ok_spec, exit_fn=codes.append)
    assert codes == [1]


def test_browser_opens_only_for_this_process():
    opened = []
    ev = threading.Event()
    ok = {'status': 'ok', 'pid': 42}
    assert lc.wait_and_open('u', 'h', ev, 42, fetch=lambda u: ok, opener=opened.append,
                            sleep=lambda s: None) is True
    assert opened == ['u']
    other = []
    assert lc.wait_and_open('u', 'h', ev, 42, fetch=lambda u: {'status': 'ok', 'pid': 7},
                            opener=other.append, sleep=lambda s: None, attempts=3) is False
    assert other == []


def test_browser_not_opened_when_cancelled_or_unreachable():
    opened = []
    ev = threading.Event()
    ev.set()
    assert lc.wait_and_open('u', 'h', ev, 1, fetch=lambda u: {'status': 'ok', 'pid': 1},
                            opener=opened.append, sleep=lambda s: None) is False

    def down(url):
        raise OSError('refused')
    assert lc.wait_and_open('u', 'h', threading.Event(), 1, fetch=down, opener=opened.append,
                            sleep=lambda s: None, attempts=3) is False
    assert opened == []


def test_server_main_cancels_browser_on_bind_failure(monkeypatch):
    import uvicorn
    import server
    monkeypatch.delenv('T2A_NO_BROWSER', raising=False)
    monkeypatch.setattr(server, 'launch_preflight', lambda: 0)
    seen = []
    monkeypatch.setattr(server._lc, 'wait_and_open', lambda **kw: seen.append(kw['cancel'].wait(5)))
    monkeypatch.setattr(server._lc, 'report_bind_failure', lambda *a, **k: None)

    def boom(app, **kw):
        raise SystemExit(1)
    monkeypatch.setattr(uvicorn, 'run', boom)
    with pytest.raises(SystemExit) as exc:
        server.main()
    assert exc.value.code == 1
    deadline = time.time() + 3
    while not seen and time.time() < deadline:
        time.sleep(0.02)
    assert seen == [True]


def test_server_main_exits_nonzero_when_preflight_fails(monkeypatch):
    import uvicorn
    import server
    monkeypatch.setattr(server, 'launch_preflight', lambda: 1)
    ran = []
    monkeypatch.setattr(uvicorn, 'run', lambda app, **kw: ran.append(kw))
    with pytest.raises(SystemExit) as exc:
        server.main()
    assert exc.value.code == 1 and ran == []


def _gone(*names):
    return lambda name: None if name in names else object()


def test_missing_num2words_gets_plain_install_guidance(tmp_path):
    out = []
    code = lc.run_preflight(port=8765, env=win_env(tmp_path), out=out.append, probe=lambda p: True,
                            find_spec=_gone('num2words'), platform='win32')
    text = '\n'.join(out)
    assert code == 1 and 'num2words' in text and 'Install Text2Audio.bat' in text
    assert 'python-multipart' not in text and 'Traceback' not in text


def test_missing_python_multipart_gets_plain_install_guidance(tmp_path):
    out = []
    code = lc.run_preflight(port=8765, env=win_env(tmp_path), out=out.append, probe=lambda p: True,
                            find_spec=_gone('python_multipart', 'multipart'), platform='win32')
    text = '\n'.join(out)
    assert code == 1 and 'python-multipart' in text and 'Install Text2Audio.bat' in text
    assert 'num2words' not in text and 'Traceback' not in text


def test_either_multipart_module_name_satisfies_the_check():
    assert lc.missing_dependencies(_gone('multipart')) == []
    assert lc.missing_dependencies(_gone('python_multipart')) == []
    assert lc.missing_dependencies(_gone('python_multipart', 'multipart')) == ['python-multipart']
    assert lc.missing_dependencies(_gone('num2words')) == ['num2words']


def test_bootstrap_exits_for_each_new_eager_dependency(tmp_path):
    for gone in (('num2words',), ('python_multipart', 'multipart')):
        out, codes = [], []
        lc.bootstrap_or_exit(find_spec=_gone(*gone), env=win_env(tmp_path), out=out.append,
                             exit_fn=codes.append, platform='win32')
        assert codes == [1] and 'Log file: "' in out[1]


@pytest.mark.parametrize('blocked, shown', [(('num2words',), 'num2words'),
                                            (('python_multipart', 'multipart'), 'python-multipart')])
def test_importing_server_stops_friendly_before_external_imports(tmp_path, blocked, shown):
    import subprocess
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = (
        'import sys, importlib.abc\n'
        'class B(importlib.abc.MetaPathFinder):\n'
        '    def find_spec(self, name, path, target=None):\n'
        '        if name in %r:\n'
        '            raise ModuleNotFoundError(name)\n'
        'sys.meta_path.insert(0, B())\n'
        'import server\n' % (blocked,))
    env = dict(os.environ, T2A_LOG_DIR=str(tmp_path / 'logs'))
    done = subprocess.run([sys.executable, '-c', code], cwd=root, env=env,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 1
    assert shown in done.stdout and 'Install Text2Audio.bat' in done.stdout
    assert 'Traceback' not in done.stderr


def _run_main_with_fake_uvicorn(monkeypatch, tmp_path, fake_run):
    import uvicorn
    import server
    monkeypatch.setenv('T2A_NO_BROWSER', '1')
    monkeypatch.setenv('T2A_LOG_DIR', str(tmp_path / 'My Logs'))
    monkeypatch.setattr(server, 'launch_preflight', lambda: 0)
    monkeypatch.setattr(uvicorn, 'run', fake_run)
    with pytest.raises(SystemExit) as exc:
        server.main()
    return exc.value.code, tmp_path / 'My Logs' / 'launch.log'


def test_bind_race_uvicorn_error_goes_to_quoted_log_not_console(monkeypatch, tmp_path, capsys):
    import logging

    def fake_run(app, **kw):
        logging.getLogger('uvicorn.error').error(OSError(
            10048, "error while attempting to bind on address ('127.0.0.1', 8765): only one usage"))
        raise SystemExit(1)

    code, log = _run_main_with_fake_uvicorn(monkeypatch, tmp_path, fake_run)
    seen = capsys.readouterr()
    assert code == 1
    assert 'Errno' not in seen.out + seen.err and 'Traceback' not in seen.out + seen.err
    assert 'could not start on port 8765' in seen.out
    assert 'Log file: "%s"' % log in seen.out
    assert 'Errno 10048' in log.read_text(encoding='utf-8')


def test_unrelated_startup_failure_is_logged_and_not_called_port_busy(monkeypatch, tmp_path, capsys):
    import logging

    def fake_run(app, **kw):
        logging.getLogger('uvicorn.error').error('lifespan exploded')
        raise SystemExit(1)

    code, log = _run_main_with_fake_uvicorn(monkeypatch, tmp_path, fake_run)
    seen = capsys.readouterr()
    assert code == 1
    assert 'could not start on port' not in seen.out and 'already in use' not in seen.out
    assert 'Log file: "%s"' % log in seen.out
    assert 'lifespan exploded' in log.read_text(encoding='utf-8')


def test_bind_error_stays_visible_when_no_log_can_be_written(monkeypatch, tmp_path):
    import io
    import logging
    from backend import launch_checks as impl

    def deny(*a, **k):
        raise OSError('no write')

    monkeypatch.setattr(impl.logging, 'FileHandler', deny)
    env = {'T2A_LOG_DIR': str(tmp_path / 'a'), 'HOME': str(tmp_path), 'USERPROFILE': str(tmp_path),
           'LOCALAPPDATA': str(tmp_path), 'XDG_STATE_HOME': str(tmp_path)}
    stream = io.StringIO()
    state = impl.setup_server_logging(env=env, platform='linux', stream=stream)
    try:
        logging.getLogger('uvicorn.error').error(OSError(98, 'error while attempting to bind'))
    finally:
        state.close()
    assert state.written is False and state.bind_error is True
    assert 'Errno 98' in stream.getvalue()


def test_launch_helper_ships_in_wheel_without_scripts_package(monkeypatch):
    import importlib
    import re
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    text = (root / 'pyproject.toml').read_text(encoding='utf-8')
    wheel = text[text.index('[tool.hatch.build.targets.wheel]'):]
    include = re.search(r'include\s*=\s*\[(.*?)\]', wheel, re.S).group(1)
    assert '"backend"' in include and '"server.py"' in include and 'scripts' not in include
    assert 'from scripts' not in (root / 'server.py').read_text(encoding='utf-8')
    assert (root / 'backend' / 'launch_checks.py').is_file()
    import server
    monkeypatch.setitem(sys.modules, 'scripts', None)
    monkeypatch.setitem(sys.modules, 'scripts.launch_checks', None)
    importlib.reload(server)
    assert server._lc is not None and server._lc.__name__ == 'backend.launch_checks'


def test_installed_layout_still_runs_preflight_and_opens_browser(monkeypatch, tmp_path):
    import importlib
    import sys
    import uvicorn
    import server
    monkeypatch.setitem(sys.modules, 'scripts', None)
    monkeypatch.setitem(sys.modules, 'scripts.launch_checks', None)
    importlib.reload(server)
    monkeypatch.delenv('T2A_NO_BROWSER', raising=False)
    checked, opened = [], []
    monkeypatch.setattr(server._lc, 'run_preflight', lambda **kw: checked.append(kw) or 0)
    monkeypatch.setattr(server._lc, 'wait_and_open', lambda **kw: opened.append(kw['url']))
    monkeypatch.setattr(uvicorn, 'run', lambda app, **kw: None)
    server.main()
    deadline = time.time() + 3
    while not opened and time.time() < deadline:
        time.sleep(0.02)
    assert checked == [{'port': server.BIND_PORT}]
    assert opened == ['http://127.0.0.1:%d' % server.BIND_PORT]
