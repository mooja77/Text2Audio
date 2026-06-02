"""Convert an ordered list of Markdown chapter files into a single book .txt
for Text2Audio.

Each input file's first `# H1` becomes the chapter title (used as the M4B
chapter marker). A clean spoken "Chapter N. Title." line is added to the start
of each chapter's narrated text. All Markdown syntax is stripped so the narrator
never reads `#`, `*`, links, etc. aloud. Chapters are separated by the `## `
marker that Text2Audio's parser splits on.

Usage:
    python md_to_book.py <output.txt> <file1.md> <file2.md> ...
"""
import os
import re
import sys

_HR = re.compile(r"^\s*([-*_]\s*){3,}$")           # scene break / horizontal rule
_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def clean_markdown(text: str) -> str:
    out = []
    for ln in text.splitlines():
        s = ln.rstrip()
        if _HR.match(s):
            out.append("")                          # scene break -> pause
            continue
        s = re.sub(r"<!--.*?-->", "", s)            # html comments
        s = re.sub(r"^\s*>\s?", "", s)              # blockquote marker
        s = re.sub(r"^\s*#{1,6}\s*", "", s)         # heading hashes -> keep text
        s = re.sub(r"^\s*[-*+]\s+", "", s)          # bullet marker
        s = re.sub(r"^\s*\d+\.\s+", "", s)          # numbered-list marker
        s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)  # images
        s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)  # links -> text
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)    # **bold**
        s = re.sub(r"__([^_]+)__", r"\1", s)        # __bold__
        s = re.sub(r"\*([^*]+)\*", r"\1", s)        # *italic*
        s = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", s)  # _italic_
        s = s.replace("`", "")                      # inline code ticks
        out.append(s)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)          # collapse blank runs
    return text.strip()


def _marker_title(title: str) -> str:
    # Drop a trailing parenthetical POV tag, e.g. "(Mick)".
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()


def _spoken_heading(marker_title: str) -> str:
    # "Chapter 1 - Ledger Morning" -> "Chapter 1. Ledger Morning."
    spoken = marker_title.replace(" - ", ". ").replace(" – ", ". ")
    if not spoken.endswith((".", "!", "?")):
        spoken += "."
    return spoken


def convert_file(path: str) -> tuple[str, str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    m = _H1.search(raw)
    if m:
        title = m.group(1).strip()
        raw = raw[:m.start()] + raw[m.end():]       # remove the H1 from body
    else:
        title = os.path.splitext(os.path.basename(path))[0]
    marker = _marker_title(title)
    body = clean_markdown(raw)
    spoken = _spoken_heading(marker)
    return marker, f"{spoken}\n\n{body}"


def build(output_path: str, md_files: list[str]) -> None:
    sections = []
    for path in md_files:
        marker, narrated = convert_file(path)
        sections.append(f"## {marker}\n{narrated}")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(sections) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    build(sys.argv[1], sys.argv[2:])
    print(f"Wrote {sys.argv[1]} from {len(sys.argv) - 2} file(s).")
