import pytest

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


@pytest.mark.parametrize("text, expected", [
    ("£1,250.75", "one thousand, two hundred and fifty pounds and seventy-five pence"),
    ("$3,000", "three thousand dollars"),
    ("€12.50", "twelve euro and fifty cents"),
    ("£1.01", "one pound and one penny"),
    ("$1.01", "one dollar and one cent"),
    ("€1.01", "one euro and one cent"),
    ("£1999", "one thousand, nine hundred and ninety-nine pounds"),
    ("£0.75", "seventy-five pence"),
    ("$0.05", "five cents"),
    ("£0.01", "one penny"),
    ("$0.01", "one cent"),
    ("€0.01", "one cent"),
    ("€0.50", "fifty cents"),
    ("£1", "one pound"),
    ("$1", "one dollar"),
    ("€1", "one euro"),
    ("£2.00", "two pounds"),
    ("$3,000.00", "three thousand dollars"),
    ("€12.00", "twelve euro"),
    ("£0", "zero pounds"),
    ("$0.00", "zero dollars"),
    ("€0.00", "zero euro"),
    ("£1.5", "one pound and fifty pence"),
    ("$0.5", "fifty cents"),
    ("$3,000.50", "three thousand dollars and fifty cents"),
    ("Pay £1,250.75.", "Pay one thousand, two hundred and fifty pounds and seventy-five pence."),
    ("£1.01, $0.05 and €12.50.", "one pound and one penny, five cents and twelve euro and fifty cents."),
])
def test_normalize_currency_amounts(text, expected):
    assert normalize_text(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("1,000,000", "one million"),
    ("1,250", "one thousand, two hundred and fifty"),
    ("3,000", "three thousand"),
    ("1,999", "one thousand, nine hundred and ninety-nine"),
    ("There were 12,345 people.", "There were twelve thousand, three hundred and forty-five people."),
    ("1, 2, 3", "one, two, three"),
])
def test_normalize_comma_separated_numbers(text, expected):
    assert normalize_text(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("1999", "nineteen ninety-nine"),
    ("1801", "eighteen oh-one"),
    ("the 3rd", "the third"),
    # Preserve the established convention: TTS handles times, decimals and %.
    ("3:30", "3:30"),
    ("12:05", "12:05"),
    ("50%", "50%"),
    ("12.5%", "12.5%"),
    ("3.5", "3.5"),
])
def test_normalize_preserves_special_number_conventions(text, expected):
    assert normalize_text(text) == expected


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
