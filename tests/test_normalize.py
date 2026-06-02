from pipeline.normalize import (
    expand_numbers, expand_abbreviations, apply_pronunciations, normalize_text,
    BUILTIN_PRONUNCIATIONS,
)


def test_expand_year():
    assert "eighteen oh-one" in expand_numbers("It was 1801 then.")


def test_expand_cardinal():
    assert "forty-two" in expand_numbers("There were 42 men.")


def test_expand_ordinal():
    assert "third" in expand_numbers("the 3rd of May")


def test_numbers_skip_currency_time_decimal():
    assert expand_numbers("$5 at 3:30 costs 3.5") == "$5 at 3:30 costs 3.5"


def test_abbreviations_basic():
    assert expand_abbreviations("Mr. Smith and Dr Jones") == "Mister Smith and Doctor Jones"


def test_abbreviations_case_insensitive():
    assert expand_abbreviations("mrs Murphy") == "Missus Murphy"


def test_ampersand():
    assert expand_abbreviations("Smith & Co") == "Smith and Co"


def test_pronunciations_whole_word_only():
    rules = {"foo": "bar"}
    assert apply_pronunciations("FOO foofighter", rules) == "bar foofighter"


def test_pronunciations_empty_rules_noop():
    assert apply_pronunciations("hello", {}) == "hello"


def test_normalize_text_custom_overrides_builtin():
    key = next(iter(BUILTIN_PRONUNCIATIONS))
    out = normalize_text(key.capitalize(), custom_rules={key: "OVERRIDDEN"})
    assert "OVERRIDDEN" in out


def test_normalize_text_runs_all_layers():
    rules = {"smith": "Smyth"}
    out = normalize_text("Mr Smith owed 42 pounds in 1801.", custom_rules=rules)
    assert "Mister" in out and "Smyth" in out and "forty-two" in out and "eighteen oh-one" in out
