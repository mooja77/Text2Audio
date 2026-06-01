from pipeline.parse import parse_chapters, Chapter


def test_explicit_markers_split_and_title():
    text = "## Intro\nHello world.\n## Chapter Two\nMore text here."
    chapters = parse_chapters(text)
    assert chapters == [
        Chapter("Intro", "Hello world."),
        Chapter("Chapter Two", "More text here."),
    ]


def test_autodetect_chapter_headings():
    text = "Chapter 1\nThe beginning.\n\nChapter 2\nThe middle."
    chapters = parse_chapters(text)
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
    assert chapters[0].text == "The beginning."
    assert chapters[1].text == "The middle."


def test_autodetect_allcaps_heading():
    text = "PROLOGUE\n\nIt was a dark night.\n\nTHE END\n\nThat is all."
    chapters = parse_chapters(text)
    assert [c.title for c in chapters] == ["PROLOGUE", "THE END"]


def test_text_before_first_heading_becomes_introduction():
    text = "Front matter line.\nChapter 1\nReal content."
    chapters = parse_chapters(text)
    assert chapters[0] == Chapter("Introduction", "Front matter line.")
    assert chapters[1] == Chapter("Chapter 1", "Real content.")


def test_no_headings_single_chapter_uses_default_title():
    text = "Just a blob of text.\nWith two lines."
    chapters = parse_chapters(text, default_title="My Book")
    assert len(chapters) == 1
    assert chapters[0].title == "My Book"
    assert "blob of text" in chapters[0].text


def test_empty_input_returns_empty_list():
    assert parse_chapters("   \n  \n") == []
