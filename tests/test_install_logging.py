"""Product-log and language-repair regressions (all mocked: no network, winget or GPU)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import install_support as ins  # noqa: E402


def _env(tmp_path, log_dir):
    home = tmp_path / "fb home"
    return {"T2A_LOG_DIR": str(log_dir), "LOCALAPPDATA": str(home), "XDG_STATE_HOME": str(home),
            "HOME": str(home), "USERPROFILE": str(home)}


def _boom_stage(monkeypatch):
    def hw(rep, post, **kw):
        rep.say("first diagnostic line")
        rep.raw("raw pip output line")
        raise RuntimeError("kaput")
    monkeypatch.setattr(ins, "stage_hardware", hw)


def test_log_is_quoted_with_spaces_and_keeps_lines_after_a_crash(tmp_path, monkeypatch):
    _boom_stage(monkeypatch)
    log_dir = tmp_path / "My Logs"
    out = []
    code = ins.main(["--stage", "pre"], out=out.append, env=_env(tmp_path, log_dir))
    expected = log_dir / "install.log"
    assert code == 1
    assert 'Log file: "%s"' % expected in "\n".join(out)
    text = expected.read_text(encoding="utf-8")
    assert "first diagnostic line" in text and "raw pip output line" in text and "kaput" in text


def test_say_persists_before_console_output(tmp_path):
    log = tmp_path / "x y" / "install.log"
    log.parent.mkdir()

    def broken(text):
        raise KeyboardInterrupt
    rep = ins.Reporter(broken, str(log))
    with pytest.raises(KeyboardInterrupt):
        rep.say("downloading 40%")
    assert "downloading 40%" in log.read_text(encoding="utf-8")


def test_unwritable_log_dir_falls_back_to_per_user_folder(tmp_path, monkeypatch):
    _boom_stage(monkeypatch)
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    out = []
    ins.main(["--stage", "pre"], out=out.append, env=_env(tmp_path, blocker / "sub"))
    text = "\n".join(out)
    assert "could not be written" not in text
    line = [l for l in out if l.startswith('Log file: "')][-1]
    path = Path(line[len('Log file: "'):-1])
    assert "fb home" in str(path) and path.name == "install.log"
    assert "first diagnostic line" in path.read_text(encoding="utf-8")


def test_install_ps1_shared_log_variable_is_honoured(tmp_path):
    shared = tmp_path / "shared dir" / "install.log"
    path, written = ins.open_install_log({"T2A_INSTALL_LOG": str(shared), "T2A_LOG_DIR": str(tmp_path / "other")})
    assert written and path == str(shared) and shared.is_file()


def test_no_writable_log_is_reported_not_hidden(tmp_path, monkeypatch):
    _boom_stage(monkeypatch)
    monkeypatch.setattr(ins, "open_install_log", lambda env=None, platform=None: (str(tmp_path / "nolog" / "install.log"), False))
    out = []
    assert ins.main(["--stage", "pre"], out=out.append) == 1
    assert "could not be written" in "\n".join(out)


# ---- language repair ----------------------------------------------------
def test_healthy_exact_version_skips_network():
    calls = []
    rep = ins.Reporter(lambda t: None)
    assert ins.stage_language(rep, run=lambda c: calls.append(c) or (0, ""), ready=lambda: True) is True
    assert not any("pip" in c for c in calls)


def test_same_version_broken_load_is_repaired_without_dependency_churn():
    state, calls = {"fixed": False}, []

    def run(cmd):
        calls.append(cmd)
        if "pip" in cmd:
            state["fixed"] = True
            return 0, "Successfully installed en_core_web_sm-3.8.0"
        return (0 if state["fixed"] else 1), "OSError: [E050] Can't find model"
    rep = ins.Reporter(lambda t: None)
    assert ins.stage_language(rep, run=run, ready=lambda: True) is True
    pip = [c for c in calls if "pip" in c]
    assert len(pip) == 1
    assert "--force-reinstall" in pip[0] and "--no-deps" in pip[0]
    assert pip[0][-1] == ins.LANGUAGE_URL and "sha256=" in ins.LANGUAGE_URL
    assert "pip" not in calls[-1]  # spacy.load is verified after the repair


def test_repair_that_still_fails_to_load_is_reported():
    rep = ins.Reporter(lambda t: None)
    run = lambda c: (0, "ok") if "pip" in c else (1, "still broken")
    assert ins.stage_language(rep, run=run, ready=lambda: True) is False
    assert "could not be installed or loaded" in "\n".join(rep.lines)


def test_missing_or_wrong_version_gets_a_plain_install():
    state, calls = {"ok": False}, []

    def run(cmd):
        calls.append(cmd)
        if "pip" in cmd:
            state["ok"] = True
            return 0, "installed"
        return (0 if state["ok"] else 1), ""
    rep = ins.Reporter(lambda t: None)
    assert ins.stage_language(rep, run=run, ready=lambda: state["ok"]) is True
    pip = [c for c in calls if "pip" in c][0]
    assert "--force-reinstall" not in pip and pip[-1] == ins.LANGUAGE_URL


# ---- install.ps1 structure (PowerShell cannot run here; root runs the real probes) ----
def _ps():
    return (ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")


def test_ps1_creates_log_before_python_discovery_and_prints_quoted_path():
    text = _ps()
    assert text.index("$script:LogPath = Initialize-InstallLog") < text.index("$pyInfo = Find-Python")
    assert "T2A_LOG_DIR" in text and 'Log file: "' in text
    assert text.isascii()  # Windows PowerShell 5.1 reads BOM-less files as ANSI


def test_ps1_failure_path_prints_log_and_exits_nonzero():
    text = _ps()
    body = text[text.index("function Fail"):]
    body = body[:body.index("\nfunction ", 5)]
    assert "Show-LogPath" in body and "exit 1" in body
    assert "UNEXPECTED ERROR" in text and "exit 0" in text


def test_ps1_captures_native_output_and_keeps_gate_before_done():
    text = _ps()
    assert "Invoke-Logged" in text and "2>&1" in text and "[stderr]" in text and "LASTEXITCODE" in text
    assert text.count("Done!") == 1
    gate = text.index('foreach ($stage in "prepare", "post", "verify")')
    assert gate < text.index("Done!") and gate < text.index("CreateShortcut")
    assert text.index("--stage\", \"pre\"") < text.index("torch==2.6.0")
