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
