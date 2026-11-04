"""Normalize text before TTS: numbers, abbreviations, and pronunciations."""
import re

from num2words import num2words

# Unambiguous abbreviations only (skip "St" — Saint vs Street).
ABBREVIATIONS = {
    "mr": "Mister", "mrs": "Missus", "ms": "Miss", "dr": "Doctor",
    "capt": "Captain", "lt": "Lieutenant", "col": "Colonel", "sgt": "Sergeant",
    "gen": "General", "rev": "Reverend", "hon": "Honourable",
}

# Starter respellings for the Cork novel's tricky names/places. Plain phonetic
# spellings (no IPA); the user overrides via the Pronounce tab. Keys lowercase.
BUILTIN_PRONUNCIATIONS = {
    "carrigaline": "Carrig a line",
    "owenabue": "Owen a boo",
    "shanbally": "Shan bally",
    "mardyke": "Mar dyke",
    "fitzgibbon": "Fitz gibbon",
    "zubieta": "Zoo bee eta",
    "hegarty": "Heg arty",
    "hanratty": "Han ratty",
    "danaher": "Dan a her",
}

_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)"
_MONEY_RE = re.compile(r"([£$€])(" + _NUMBER + r"(?:\.\d{1,2})?)(?![\w]|\.\d)")
_CURRENCIES = {"£": "GBP", "$": "USD", "€": "EUR"}
_NUM_RE = re.compile(r"(?<![\$\d.:,])\b(" + _NUMBER + r")(st|nd|rd|th)?\b(?![\d:%]|,\d)(?!\.\d)", re.IGNORECASE)


def expand_numbers(text: str) -> str:
    def repl(m):
        digits, ordinal = m.group(1), m.group(2)
        n = int(digits.replace(",", ""))
        try:
            if ordinal:
                return num2words(n, to="ordinal")
            if len(digits) == 4 and 1500 <= n <= 2099:
                return num2words(n, to="year")
            return num2words(n)
        except Exception:
            return m.group(0)
    return _NUM_RE.sub(repl, text)


_ABBR_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in ABBREVIATIONS) + r")\b\.?",
    re.IGNORECASE,
)


def expand_abbreviations(text: str) -> str:
    text = re.sub(r"(?<=\s)&(?=\s)", "and", text)  # standalone ampersand
    return _ABBR_RE.sub(lambda m: ABBREVIATIONS[m.group(1).lower()], text)


def apply_pronunciations(text: str, rules: dict) -> str:
    if not rules:
        return text
    keys = sorted(rules.keys(), key=len, reverse=True)  # longest-first
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b",
                         re.IGNORECASE)
    return pattern.sub(lambda m: rules[m.group(1).lower()], text)


def normalize_text(text: str, custom_rules: dict | None = None) -> str:
    merged = {**BUILTIN_PRONUNCIATIONS,
              **{k.lower(): v for k, v in (custom_rules or {}).items()}}
    # Convert complete amounts before the general number/year expansion.
    text = _MONEY_RE.sub(
        lambda m: num2words(m.group(2).replace(",", ""), to="currency",
                            currency=_CURRENCIES[m.group(1)], separator=" and"),
        text,
    )
    text = expand_numbers(text)
    text = expand_abbreviations(text)
    text = apply_pronunciations(text, merged)
    return text
