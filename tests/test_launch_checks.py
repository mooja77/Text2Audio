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
