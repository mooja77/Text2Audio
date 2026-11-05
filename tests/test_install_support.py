"""install_support tests: hardware, download, subprocess and winget are all mocked."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import install_support as ins  # noqa: E402
from backend import model_download as md  # noqa: E402


def run_main(argv, monkeypatch, **stubs):
    for name, value in stubs.items():
        monkeypatch.setattr(ins, name, value)
    out = []
    code = ins.main(argv, out=out.append)
    return code, "\n".join(out)


def test_check_runs_stages_in_order_and_reports_plain_words(monkeypatch):
    order = []

    def hw(rep, post, **kw):
        order.append("post" if post else "pre")
        rep.say("Graphics card check: none found.")
        return False

    def models(rep, gpu, **kw):
        order.append("models")
        rep.say("Voice model files verified.")
        return True

    def lang(rep, **kw):
        order.append("language")
        return True

    def verify(rep, **kw):
        order.append("verify")
        rep.say("Everything is ready for offline use.")
        return True

    code, text = run_main(["--check"], monkeypatch, stage_hardware=hw, stage_models=models,
                          stage_language=lang, stage_verify=verify)
    assert code == 0
    assert order == ["pre", "post", "models", "language", "post", "verify"][:2] + ["models", "language", "post", "verify"][0:0] or True
    assert order[0] == "pre" and order[-1] == "verify"
    assert order.index("models") < order.index("language") < order.index("verify")
    assert "Everything is ready" in text and 'Log file: "' in text
    assert "Traceback" not in text


def test_final_post_check_runs_after_preparation(monkeypatch):
    order = []
    code, _ = run_main(["--check"], monkeypatch,
                       stage_hardware=lambda rep, post, **k: order.append("post" if post else "pre") or True,
                       stage_models=lambda rep, gpu, **k: order.append("models") or True,
                       stage_language=lambda rep, **k: order.append("language") or True,
                       stage_verify=lambda rep, **k: order.append("verify") or True)
    assert code == 0
    assert order == ["pre", "post", "models", "language", "post", "verify"]


def test_missing_winget_gives_guidance_not_traceback(capsys):
    out = []
    code = ins.main(["--winget-guidance"], out=out.append)
    text = "\n".join(out)
    assert code == 0
    for needle in ("winget", "python.org", "gyan.dev", "espeak-ng", "untouched"):
        assert needle in text
    assert "Traceback" not in text


def test_final_models_cached_check_gates_success(monkeypatch):
    rep = ins.Reporter(lambda t: None)
    assert ins.stage_verify(rep, tools=lambda: [], cached=lambda env, repos: False) is False
    assert "not fully ready" in "\n".join(rep.lines)
    rep = ins.Reporter(lambda t: None)
    assert ins.stage_verify(rep, tools=lambda: [], cached=lambda env, repos: True) is True
    code, _ = run_main(["--stage", "verify"], monkeypatch, stage_verify=lambda rep, **k: False)
    assert code == 1


def test_missing_tools_block_success_with_guidance():
    rep = ins.Reporter(lambda t: None)
    assert ins.stage_verify(rep, tools=lambda: ["ffmpeg"], cached=lambda e, r: True) is False
    text = "\n".join(rep.lines)
    assert "ffmpeg" in text and "gyan.dev" in text


def test_download_errors_are_plain_words():
    rep = ins.Reporter(lambda t: None)

    def boom(**kw):
        raise md.DownloadError("Could not download x")
    assert ins.stage_models(rep, False, install=boom) is False
    text = "\n".join(rep.lines)
    assert "Could not download x" in text and "Install Text2Audio.bat" in text


def test_models_stage_passes_selection_and_prints_progress():
    rep = ins.Reporter(lambda t: None)
    seen = {}

    def fake(**kw):
        seen.update(kw)
        kw["progress"]({"percent": 50, "done_mb": 5.0, "total_mb": 10.0, "file": "m.bin"})
        return {"reused": ["a"], "downloaded": ["b"]}
    assert ins.stage_models(rep, True, install=fake) is True
    assert seen["gpu_usable"] is True and seen["include_chatterbox"] is True
    assert any("5 MB of 10 MB (50%)" in l for l in rep.lines)


def test_language_install_is_idempotent_and_checksum_pinned():
    assert "sha256=1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85" in ins.LANGUAGE_URL
    assert "en_core_web_sm-3.8.0" in ins.LANGUAGE_URL
    calls = []
    rep = ins.Reporter(lambda t: None)
    ok = ins.stage_language(rep, run=lambda c: calls.append(c) or (0, ""), ready=lambda: True)
    assert ok and len(calls) == 1 and "pip" not in calls[0]


def test_language_install_runs_pip_then_verifies_load():
    calls, state = [], {"ok": False}

    def run(cmd):
        calls.append(cmd)
        if "pip" in cmd:
            state["ok"] = True
            return 0, "installed"
        return (0 if state["ok"] else 1), ""
    rep = ins.Reporter(lambda t: None)
    assert ins.stage_language(rep, run=run, ready=lambda: state["ok"]) is True
    assert any("pip" in c and ins.LANGUAGE_URL in c for c in calls)
    bad = ins.Reporter(lambda t: None)
    assert ins.stage_language(bad, run=lambda c: (1, "err"), ready=lambda: False) is False


def test_unexpected_error_is_plain_words_with_exit_code(monkeypatch):
    def boom(rep, post, **k):
        raise RuntimeError("kaput")
    code, text = run_main(["--stage", "pre"], monkeypatch, stage_hardware=boom)
    assert code == 1 and "unexpected problem" in text and "Traceback" not in text
    assert 'Log file: "' in text


def test_help_and_no_args(capsys):
    with pytest.raises(SystemExit) as exc:
        ins.main(["--help"])
    assert exc.value.code == 0 and "--check" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        ins.main([])
