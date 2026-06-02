import json
import shutil
import subprocess

import numpy as np
import pytest

from pipeline.assemble import write_wav, build_m4b, _build_ffmetadata
from pipeline.synth import SAMPLE_RATE

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def test_ffmetadata_has_chapters_and_escapes():
    meta = _build_ffmetadata(["Intro", "Chap=Two"], [1000, 2000],
                             book_title="My Book", author="Me")
    assert ";FFMETADATA1" in meta
    assert "title=My Book" in meta
    assert meta.count("[CHAPTER]") == 2
    assert "START=0" in meta and "END=1000" in meta
    assert "START=1000" in meta and "END=3000" in meta
    assert "Chap\\=Two" in meta  # '=' escaped


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_build_m4b_produces_two_chapters(tmp_path):
    wav1 = str(tmp_path / "c1.wav")
    wav2 = str(tmp_path / "c2.wav")
    t1 = np.linspace(0, 1.0, SAMPLE_RATE, dtype=np.float32)
    t2 = np.linspace(0, 0.5, SAMPLE_RATE // 2, dtype=np.float32)
    write_wav(0.1 * np.sin(2 * np.pi * 440 * t1), wav1)   # 1.0s sine
    write_wav(0.1 * np.sin(2 * np.pi * 440 * t2), wav2)   # 0.5s sine
    out = str(tmp_path / "book.m4b")

    build_m4b([("Chapter One", wav1), ("Chapter Two", wav2)], out,
              book_title="Test Book", author="Tester")

    probe = subprocess.run(
        ["ffprobe", "-print_format", "json", "-show_chapters", out],
        capture_output=True, text=True, check=True)
    chapters = json.loads(probe.stdout)["chapters"]
    assert len(chapters) == 2
    assert chapters[0]["tags"]["title"] == "Chapter One"
    assert chapters[1]["tags"]["title"] == "Chapter Two"


def test_build_m4b_missing_ffmpeg_raises(tmp_path):
    with pytest.raises(RuntimeError):
        build_m4b([("A", "x.wav")], str(tmp_path / "o.m4b"),
                  ffmpeg="definitely-not-ffmpeg-xyz")


def test_build_m4b_applies_master_filters_and_bitrate(tmp_path, monkeypatch):
    import pipeline.assemble as asm
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        class R: pass
        return R()

    # write a real wav so duration probing works, but stub ffmpeg invocation
    import numpy as np
    from pipeline.synth import SAMPLE_RATE
    wav = str(tmp_path / "c.wav")
    asm.write_wav(np.zeros(SAMPLE_RATE, dtype=np.float32), wav)
    monkeypatch.setattr(asm.subprocess, "run", fake_run)
    monkeypatch.setattr(asm.shutil, "which", lambda x: "ffmpeg")

    asm.build_m4b([("C1", wav)], str(tmp_path / "out.m4b"), master=True)
    cmd = captured["cmd"]
    assert "-af" in cmd
    af = cmd[cmd.index("-af") + 1]
    assert "loudnorm" in af and "highpass" in af
    assert "128k" in cmd  # default bitrate


def test_build_m4b_master_false_omits_filters(tmp_path, monkeypatch):
    import pipeline.assemble as asm
    captured = {}
    monkeypatch.setattr(asm.subprocess, "run", lambda cmd, **k: captured.setdefault("cmd", cmd))
    monkeypatch.setattr(asm.shutil, "which", lambda x: "ffmpeg")
    import numpy as np
    from pipeline.synth import SAMPLE_RATE
    wav = str(tmp_path / "c.wav")
    asm.write_wav(np.zeros(SAMPLE_RATE, dtype=np.float32), wav)
    asm.build_m4b([("C1", wav)], str(tmp_path / "out.m4b"), master=False, bitrate="96k")
    cmd = captured["cmd"]
    assert "-af" not in cmd
    assert "96k" in cmd


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_build_m4b_master_true_survives_pure_silence(tmp_path):
    # loudnorm NaN on silence must not crash: fall back to a valid unmastered file.
    wav = str(tmp_path / "silent.wav")
    write_wav(np.zeros(SAMPLE_RATE, dtype=np.float32), wav)
    out = str(tmp_path / "silent.m4b")
    build_m4b([("C1", wav)], out, master=True)
    probe = subprocess.run(["ffprobe", "-print_format", "json", "-show_chapters", out],
                           capture_output=True, text=True, check=True)
    assert len(json.loads(probe.stdout)["chapters"]) == 1
