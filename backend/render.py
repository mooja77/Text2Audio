"""Orchestrate the TTS pipeline into a finished audiobook + manifest."""
import datetime
import os
import shutil

import numpy as np
import soundfile as sf

from pipeline.parse import parse_chapters
from pipeline.chunk import chunk_paragraphs
from pipeline.synth import Synthesizer, PRESET_VOICES, SAMPLE_RATE
from pipeline.assemble import write_wav, build_m4b, DEFAULT_BITRATE
from pipeline.normalize import normalize_text

WAV_SUBDIR = "wav"


def _wav_dir(library, job_id: str) -> str:
    d = os.path.join(library.new_dir(job_id), WAV_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


def _chapter_meta(chapter_wavs):
    meta, start = [], 0
    for title, wp in chapter_wavs:
        info = sf.info(wp)
        dur = int(round(info.frames / info.samplerate * 1000))
        meta.append({"title": title, "startMs": start, "endMs": start + dur})
        start += dur
    return meta


def render_audiobook(*, book_text, voice, speed, title, author, cover_path,
                     library, job_id, emit, synth_factory=Synthesizer,
                     custom_rules=None) -> dict:
    chapters = parse_chapters(book_text, default_title=title or "Audiobook")
    workdir = library.new_dir(job_id)
    try:
        return _render_into(workdir, chapters, voice=voice, speed=speed, title=title,
                            author=author, cover_path=cover_path, library=library,
                            job_id=job_id, emit=emit, synth_factory=synth_factory,
                            custom_rules=custom_rules)
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


def _render_into(workdir, chapters, *, voice, speed, title, author, cover_path,
                 library, job_id, emit, synth_factory, custom_rules=None) -> dict:
    synth = synth_factory(voice=voice, lang_code=PRESET_VOICES[voice], speed=float(speed))
    wav_dir = _wav_dir(library, job_id)

    n = len(chapters)
    chapter_wavs = []
    wav_files = []
    for i, ch in enumerate(chapters):
        emit({"type": "progress", "chapterIndex": i, "chapterCount": n,
              "chapterTitle": ch.title, "percent": round(i / max(1, n) * 100)})
        audio = synth.synth_paragraphs(chunk_paragraphs(normalize_text(ch.text, custom_rules)))
        if len(audio) == 0:
            audio = np.zeros(int(0.5 * SAMPLE_RATE), dtype=np.float32)
        rel = os.path.join(WAV_SUBDIR, f"chapter_{i + 1:03d}.wav")
        write_wav(audio, os.path.join(workdir, rel))
        chapter_wavs.append((ch.title, os.path.join(workdir, rel)))
        wav_files.append(rel)

    cover_dest = None
    if cover_path:
        cover_dest = os.path.join(workdir, "cover.jpg")
        shutil.copyfile(cover_path, cover_dest)

    out = library.audio_path(job_id)
    build_m4b(chapter_wavs, out, book_title=title or None, author=author or None,
              cover=cover_dest, master=True, bitrate=DEFAULT_BITRATE)

    chapters_meta = _chapter_meta(chapter_wavs)
    total_ms = chapters_meta[-1]["endMs"] if chapters_meta else 0

    manifest = {
        "id": job_id, "title": title or "Audiobook", "author": author or "",
        "voice": voice, "speed": float(speed),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "durationSeconds": round(total_ms / 1000, 1), "sizeBytes": os.path.getsize(out),
        "chapters": chapters_meta, "coverFile": "cover.jpg" if cover_dest else None,
        "wavKept": True, "wavFiles": wav_files, "bitrate": DEFAULT_BITRATE, "mastered": True,
    }
    library.save_manifest(job_id, manifest)
    emit({"type": "done", "libraryId": job_id, "percent": 100})
    return manifest


def remaster(library, id, *, bitrate=DEFAULT_BITRATE, master=True) -> dict:
    m = library.get(id)
    if m is None:
        raise FileNotFoundError(f"no such audiobook: {id}")
    if not m.get("wavKept") or not m.get("wavFiles"):
        raise ValueError("source audio was purged; re-render required to re-master")
    workdir = library.new_dir(id)
    chapter_wavs = [(c["title"], os.path.join(workdir, rel))
                    for c, rel in zip(m["chapters"], m["wavFiles"])]
    out = library.audio_path(id)
    build_m4b(chapter_wavs, out, book_title=m["title"] or None, author=m["author"] or None,
              cover=os.path.join(workdir, m["coverFile"]) if m.get("coverFile") else None,
              master=master, bitrate=bitrate)
    m["bitrate"] = bitrate
    m["mastered"] = master
    m["sizeBytes"] = os.path.getsize(out)
    library.save_manifest(id, m)
    return m


def purge_wavs(library, id) -> dict:
    m = library.get(id)
    if m is None:
        raise FileNotFoundError(f"no such audiobook: {id}")
    shutil.rmtree(os.path.join(library.new_dir(id), WAV_SUBDIR), ignore_errors=True)
    m["wavKept"] = False
    m["wavFiles"] = []
    library.save_manifest(id, m)
    return m
