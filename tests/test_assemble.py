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
    write_wav(np.zeros(SAMPLE_RATE, dtype=np.float32), wav1)        # 1.0s
    write_wav(np.zeros(SAMPLE_RATE // 2, dtype=np.float32), wav2)   # 0.5s
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
