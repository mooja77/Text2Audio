from pipeline.ingest import (
    clean_markdown, section_from_text, build_book_text, build_book_text_from_paths,
)
from pipeline.parse import parse_chapters


def test_clean_markdown_strips_syntax():
    md = "# Heading\n\nSome **bold** and *italic* and `code` text.\n\n---\n\n> quote\n- bullet"
    out = clean_markdown(md)
    assert "**" not in out and "*" not in out and "`" not in out
    assert "#" not in out
    assert ">" not in out
    assert "bold" in out and "italic" in out and "code" in out
    assert "bullet" in out


def test_clean_markdown_keeps_links_text_only():
    assert clean_markdown("See [the docs](http://x.com) now.") == "See the docs now."


def test_section_from_text_uses_h1_as_title():
    marker, narrated = section_from_text("Chapter01_X.md", "# Chapter 1 - Ledger Morning (Mick)\n\nHello world.")
    assert marker == "Chapter 1 - Ledger Morning"            # POV tag dropped
    assert narrated.startswith("Chapter 1. Ledger Morning.")  # spoken heading
    assert "Hello world." in narrated
    assert "#" not in narrated


def test_section_from_text_falls_back_to_filename():
    marker, narrated = section_from_text("My_Notes.txt", "Just text, no heading.")
    assert marker == "My_Notes"
    assert "Just text, no heading." in narrated


def test_build_book_text_orders_and_marks_chapters():
    sources = [
        ("a.md", "# Chapter 1 - One\n\nFirst."),
        ("b.md", "# Chapter 2 - Two\n\nSecond."),
    ]
    text = build_book_text(sources)
    chapters = parse_chapters(text)
    assert [c.title for c in chapters] == ["Chapter 1 - One", "Chapter 2 - Two"]
    assert "First." in chapters[0].text and "Second." in chapters[1].text


def test_build_book_text_from_paths(tmp_path):
    p1 = tmp_path / "c1.md"; p1.write_text("# Chapter 1 - A\n\nAlpha.", encoding="utf-8")
    p2 = tmp_path / "c2.md"; p2.write_text("# Chapter 2 - B\n\nBeta.", encoding="utf-8")
    text = build_book_text_from_paths([str(p1), str(p2)])
    chapters = parse_chapters(text)
    assert [c.title for c in chapters] == ["Chapter 1 - A", "Chapter 2 - B"]
