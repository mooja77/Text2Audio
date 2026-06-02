"""Orchestrate the TTS pipeline into a finished audiobook + manifest."""
import datetime
import os
import shutil

import numpy as np
import soundfile as sf

from pipeline.parse import parse_chapters
from pipeline.chunk import chunk_text
from pipeline.synth import Synthesizer, PRESET_VOICES, SAMPLE_RATE
from pipeline.assemble import write_wav, build_m4b


def render_audiobook(*, book_text, voice, speed, title, author, cover_path,
                     library, job_id, emit, synth_factory=Synthesizer) -> dict:
    chapters = parse_chapters(book_text, default_title=title or "Audiobook")
    workdir = library.new_dir(job_id)
    try:
        return _render_into(workdir, chapters, voice=voice, speed=speed, title=title,
                            author=author, cover_path=cover_path, library=library,
                            job_id=job_id, emit=emit, synth_factory=synth_factory)
    except Exception:
        # A render that fails partway leaves orphan WAVs and no manifest; remove
        # the whole workspace so failed runs don't accumulate junk on disk.
        shutil.rmtree(workdir, ignore_errors=True)
        raise


def _render_into(workdir, chapters, *, voice, speed, title, author, cover_path,
                 library, job_id, emit, synth_factory) -> dict:
    synth = synth_factory(voice=voice, lang_code=PRESET_VOICES[voice], speed=float(speed))

    n = len(chapters)
    chapter_wavs = []
    for i, ch in enumerate(chapters):
        emit({"type": "progress", "chapterIndex": i, "chapterCount": n,
              "chapterTitle": ch.title, "percent": round(i / max(1, n) * 100)})
        audio = synth.synth_chunks(chunk_text(ch.text))
        if len(audio) == 0:
            audio = np.zeros(int(0.5 * SAMPLE_RATE), dtype=np.float32)
        wp = os.path.join(workdir, f"chapter_{i + 1:03d}.wav")
        write_wav(audio, wp)
        chapter_wavs.append((ch.title, wp))

    cover_dest = None
    if cover_path:
        cover_dest = os.path.join(workdir, "cover.jpg")
        shutil.copyfile(cover_path, cover_dest)

    out = library.audio_path(job_id)
    build_m4b(chapter_wavs, out, book_title=title or None, author=author or None, cover=cover_dest)

    chapters_meta = []
    start = 0
    for ctitle, wp in chapter_wavs:
        info = sf.info(wp)
        dur = int(round(info.frames / info.samplerate * 1000))
        chapters_meta.append({"title": ctitle, "startMs": start, "endMs": start + dur})
        start += dur
    for _, wp in chapter_wavs:
        try:
            os.remove(wp)
        except OSError:
            pass

    manifest = {
        "id": job_id, "title": title or "Audiobook", "author": author or "",
        "voice": voice, "speed": float(speed),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "durationSeconds": round(start / 1000, 1), "sizeBytes": os.path.getsize(out),
        "chapters": chapters_meta, "coverFile": "cover.jpg" if cover_dest else None,
    }
    library.save_manifest(job_id, manifest)
    emit({"type": "done", "libraryId": job_id, "percent": 100})
    return manifest
