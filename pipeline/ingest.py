"""Convert Markdown/plain-text chapter files into a single book text for
Text2Audio. Each file's first `# H1` becomes the chapter title; Markdown syntax
is stripped; a spoken "Chapter N." heading is prepended; chapters are joined with
the `## ` marker that pipeline.parse splits on."""
import os
import re

from pipeline.parse import parse_chapters

_HR = re.compile(r"^\s*([-*_]\s*){3,}$")
_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def clean_markdown(text: str, *, preserve_leading_numbers: bool = False) -> str:
    out = []
    for ln in text.splitlines():
        s = ln.rstrip()
        if _HR.match(s):
            out.append("")
            continue
        s = re.sub(r"<!--.*?-->", "", s)
        s = re.sub(r"^\s*>\s?", "", s)
        s = re.sub(r"^\s*#{1,6}\s*", "", s)
        s = re.sub(r"^\s*[-*+]\s+", "", s)
        if not preserve_leading_numbers:
            s = re.sub(r"^\s*\d+\.\s+", "", s)
        s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
        s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        s = re.sub(r"__([^_]+)__", r"\1", s)
        s = re.sub(r"\*([^*]+)\*", r"\1", s)
        s = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", s)
        s = s.replace("`", "")
        out.append(s)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _marker_title(title: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()


def _spoken_heading(marker_title: str) -> str:
    spoken = marker_title.replace(" - ", ". ").replace(" – ", ". ")
    if not spoken.endswith((".", "!", "?")):
        spoken += "."
    return spoken


def section_from_text(filename: str, raw: str) -> tuple[str, str]:
    m = _H1.search(raw)
    if m:
        title = m.group(1).strip()
        raw = raw[:m.start()] + raw[m.end():]
    else:
        title = os.path.splitext(os.path.basename(filename))[0]
    marker = _marker_title(title)
    body = clean_markdown(raw)
    return marker, f"{_spoken_heading(marker)}\n\n{body}"


def build_book_text(sources: list[tuple[str, str]]) -> str:
    sections = []
    for filename, content in sources:
        if os.path.splitext(filename)[1].lower() in {".txt", ".md", ".markdown", ".pdf"}:
            # Detect headings before Markdown cleanup erases them. Preserve the
            # original title, including meaningful parentheticals, rather than
            # applying the POV-tag trimming used for ordinary H1 source titles.
            chapters = parse_chapters(content, default_title="")
            ordinary_h1 = len(chapters) == 1 and _H1.search(content) is not None
            if chapters and not ordinary_h1 and (len(chapters) > 1 or chapters[0].title):
                for chapter in chapters:
                    title = clean_markdown(chapter.title, preserve_leading_numbers=True)
                    narrated = f"{_spoken_heading(title)}\n\n{clean_markdown(chapter.text)}"
                    sections.append(f"## {title}\n{narrated}")
                continue
        marker, narrated = section_from_text(filename, content)
        sections.append(f"## {marker}\n{narrated}")
    return "\n\n".join(sections) + "\n"


def build_book_text_from_paths(paths: list[str]) -> str:
    sources = []
    for p in paths:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            sources.append((os.path.basename(p), f.read()))
    return build_book_text(sources)
