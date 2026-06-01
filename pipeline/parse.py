"""Parse plain-text books into chapters."""
import re
from dataclasses import dataclass

_CHAPTER_RE = re.compile(r"^\s*chapter\b.*", re.IGNORECASE)


@dataclass
class Chapter:
    title: str
    text: str


def _is_explicit_heading(line: str, token: str) -> bool:
    return line.strip().startswith(token)


def _explicit_title(line: str, token: str) -> str:
    return line.strip()[len(token):].strip()


def _is_auto_heading(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _CHAPTER_RE.match(s):
        return True
    # Short all-caps line containing at least one letter, used as a heading.
    return s.isupper() and any(ch.isalpha() for ch in s) and len(s) <= 50


def parse_chapters(text: str, marker: str = "## ", default_title: str = "Audiobook") -> list[Chapter]:
    lines = text.splitlines()
    token = marker.strip()

    use_explicit = any(_is_explicit_heading(ln, token) for ln in lines)
    if use_explicit:
        def is_heading(ln): return _is_explicit_heading(ln, token)
        def get_title(ln): return _explicit_title(ln, token)
    else:
        def is_heading(ln): return _is_auto_heading(ln)
        def get_title(ln): return ln.strip()

    chapters: list[Chapter] = []
    current_title = None
    buf: list[str] = []

    def flush(title):
        body = "\n".join(buf).strip()
        if title is None:
            if body:
                chapters.append(Chapter("Introduction", body))
        else:
            chapters.append(Chapter(title, body))

    for ln in lines:
        if is_heading(ln):
            if current_title is not None or "".join(buf).strip():
                flush(current_title)
            current_title = get_title(ln)
            buf = []
        else:
            buf.append(ln)

    if current_title is not None or "".join(buf).strip():
        flush(current_title)

    if not chapters:
        return []
    if len(chapters) == 1 and chapters[0].title == "Introduction":
        chapters[0] = Chapter(default_title, chapters[0].text)
    return chapters
