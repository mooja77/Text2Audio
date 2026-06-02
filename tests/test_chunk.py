from pipeline.chunk import chunk_text


def test_empty_returns_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_single_chunk():
    assert chunk_text("Hello there. How are you?") == ["Hello there. How are you?"]


def test_groups_sentences_under_limit():
    text = "One sentence here. Two sentence here. Three sentence here."
    chunks = chunk_text(text, max_chars=25)
    assert len(chunks) == 3
    assert all(len(c) <= 25 for c in chunks)


def test_long_sentence_split_on_word_boundary():
    text = "word " * 50  # one very long "sentence", 250 chars
    chunks = chunk_text(text.strip(), max_chars=40)
    assert all(len(c) <= 40 for c in chunks)
    # No word is ever broken: rejoining yields only whole "word" tokens.
    assert all(tok == "word" for c in chunks for tok in c.split())


def test_whitespace_is_normalized():
    assert chunk_text("Hello\n\n  world.") == ["Hello world."]


from pipeline.chunk import chunk_paragraphs


def test_chunk_paragraphs_groups_by_blank_line():
    text = "First para sentence one. Sentence two.\n\nSecond para only."
    paras = chunk_paragraphs(text)
    assert len(paras) == 2
    assert all(isinstance(p, list) for p in paras)
    assert "Second para only." in paras[1][0]


def test_chunk_paragraphs_respects_max_chars():
    text = "One sentence here. Two sentence here. Three sentence here."
    paras = chunk_paragraphs(text, max_chars=25)
    flat = [c for p in paras for c in p]
    assert all(len(c) <= 25 for c in flat)
    assert len(paras) == 1  # single paragraph, multiple chunks
    assert len(paras[0]) == 3


def test_chunk_paragraphs_drops_empty():
    text = "\n\n  \n\nReal text.\n\n\n"
    paras = chunk_paragraphs(text)
    assert len(paras) == 1 and paras[0] == ["Real text."]


def test_chunk_paragraphs_empty_input():
    assert chunk_paragraphs("   \n\n  ") == []
