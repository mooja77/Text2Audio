"""The drop/import path must retain chapter boundaries, not just the words."""
from pathlib import Path

from pipeline.documents import document_to_sources
from pipeline.ingest import build_book_text
from pipeline.parse import parse_chapters


FIXTURES = Path(__file__).parent / 'fixtures' / 'public-domain'
TITLES = ['CHAPTER 1. The Fox and the Grapes',
          'CHAPTER 2. The Lion and the Mouse',
          'CHAPTER 3. The Tortoise and the Hare']


def imported_chapters(filename, data):
    return parse_chapters(build_book_text(document_to_sources(filename, data)))


def test_txt_drop_preserves_numbered_chapters():
    path = FIXTURES / 'aesop-three-fables.txt'
    chapters = imported_chapters(path.name, path.read_bytes())
    assert [c.title for c in chapters] == TITLES
    assert 'famished fox' in chapters[0].text
    assert 'lion was awakened' in chapters[1].text
    assert 'hare one day' in chapters[2].text


def test_pdf_drop_preserves_numbered_chapters():
    path = FIXTURES / 'aesop-three-fables.pdf'
    chapters = imported_chapters(path.name, path.read_bytes())
    assert [c.title for c in chapters] == TITLES
    assert 'famished fox' in chapters[0].text
    assert 'lion was awakened' in chapters[1].text
    assert 'hare one day' in chapters[2].text


def test_markdown_drop_preserves_explicit_chapters_and_preamble():
    chapters = imported_chapters('fables.md', b'An introduction.\n\n## Fox\nGrapes.\n\n## Lion\nMouse.')
    assert [c.title for c in chapters] == ['Introduction', 'Fox', 'Lion']
    assert 'An introduction.' in chapters[0].text
    assert 'Grapes.' in chapters[1].text
    assert 'Mouse.' in chapters[2].text


def test_unchaptered_text_keeps_existing_import_contract():
    assert document_to_sources('note.txt', b'One short note.') == [('note.txt', 'One short note.')]
    assert [c.title for c in imported_chapters('note.txt', b'One short note.')] == ['note']


def test_detected_chapter_titles_keep_meaningful_parentheses():
    chapters = imported_chapters('book.txt', b'CHAPTER 1 (Summer 1914)\nAlpha.\nCHAPTER 2 (Winter 1915)\nBeta.')
    assert [c.title for c in chapters] == ['CHAPTER 1 (Summer 1914)', 'CHAPTER 2 (Winter 1915)']
    assert 'Summer 1914' in chapters[0].text and 'Alpha.' in chapters[0].text
    assert 'Winter 1915' in chapters[1].text and 'Beta.' in chapters[1].text


def test_single_recognised_chapter_keeps_its_title():
    chapters = imported_chapters('book.txt', b'CHAPTER 1\nOne short note.')
    assert [c.title for c in chapters] == ['CHAPTER 1']
    assert 'One short note.' in chapters[0].text


def test_all_caps_chapters_keep_order_and_text():
    chapters = imported_chapters('book.txt', b'THE FOX\nGrapes.\nTHE LION\nMouse.')
    assert [c.title for c in chapters] == ['THE FOX', 'THE LION']
    assert 'Grapes.' in chapters[0].text and 'Mouse.' in chapters[1].text


def test_ordinary_uppercase_h1_keeps_existing_pov_title_contract():
    chapters = imported_chapters('chapter.md', b'# CHAPTER ONE (POV)\n\nBody.')
    assert [c.title for c in chapters] == ['CHAPTER ONE']
    assert chapters[0].text == 'CHAPTER ONE.\n\nBody.'


def test_detected_uppercase_markdown_headings_have_no_spoken_markup():
    chapters = imported_chapters('book.md', b'# TITLE\n\nCHAPTER 1\nAlpha.\nCHAPTER 2\nBeta.')
    assert [c.title for c in chapters] == ['TITLE', 'CHAPTER 1', 'CHAPTER 2']
    assert all('#' not in c.title and '#' not in c.text for c in chapters)
