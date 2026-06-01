"""Assemble per-chapter WAVs into a chaptered .m4b with ffmpeg."""
import os
import shutil
import subprocess

import soundfile as sf

from pipeline.synth import SAMPLE_RATE


def write_wav(audio, path: str, sample_rate: int = SAMPLE_RATE) -> str:
    sf.write(path, audio, sample_rate)
    return path


def _duration_ms(wav_path: str) -> int:
    info = sf.info(wav_path)
    return int(round(info.frames / info.samplerate * 1000))


def _escape(value: str) -> str:
    # Escape ffmetadata special characters.
    for ch in ("\\", "=", ";", "#", "\n"):
        value = value.replace(ch, "\\" + ch)
    return value


def _build_ffmetadata(titles, durations_ms, book_title=None, author=None) -> str:
    lines = [";FFMETADATA1"]
    if book_title:
        lines.append(f"title={_escape(book_title)}")
    if author:
        lines.append(f"artist={_escape(author)}")
    start = 0
    for title, dur in zip(titles, durations_ms):
        end = start + dur
        lines += ["", "[CHAPTER]", "TIMEBASE=1/1000",
                  f"START={start}", f"END={end}", f"title={_escape(title)}"]
        start = end
    return "\n".join(lines) + "\n"


def build_m4b(chapter_wavs, output_path: str, book_title=None, author=None,
              cover=None, ffmpeg: str = "ffmpeg") -> str:
    if shutil.which(ffmpeg) is None:
        raise RuntimeError(
            f"'{ffmpeg}' not found. Install ffmpeg and ensure it is on PATH "
            "(see README).")

    titles = [t for t, _ in chapter_wavs]
    paths = [p for _, p in chapter_wavs]
    durations = [_duration_ms(p) for p in paths]

    workdir = os.path.dirname(os.path.abspath(output_path)) or "."
    concat_path = os.path.join(workdir, "_concat.txt")
    meta_path = os.path.join(workdir, "_ffmeta.txt")

    with open(concat_path, "w", encoding="utf-8") as f:
        for p in paths:
            safe = os.path.abspath(p).replace("'", r"'\''")
            f.write(f"file '{safe}'\n")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(_build_ffmetadata(titles, durations, book_title, author))

    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
           "-i", meta_path]
    if cover:
        cmd += ["-i", cover]
    cmd += ["-map", "0:a", "-map_metadata", "1"]
    if cover:
        cmd += ["-map", "2:v", "-disposition:v", "attached_pic", "-c:v", "mjpeg"]
    cmd += ["-c:a", "aac", "-b:a", "64k", output_path]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    finally:
        for tmp in (concat_path, meta_path):
            if os.path.exists(tmp):
                os.remove(tmp)
    return output_path
