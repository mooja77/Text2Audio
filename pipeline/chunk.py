"""Split chapter text into TTS-sized chunks on sentence boundaries."""
import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _hard_split(sentence: str, max_chars: int) -> list[str]:
    pieces, piece = [], ""
    for word in sentence.split(" "):
        if piece and len(piece) + 1 + len(word) > max_chars:
            pieces.append(piece)
            piece = word
        else:
            piece = f"{piece} {word}".strip()
    if piece:
        pieces.append(piece)
    return pieces


def chunk_text(text: str, max_chars: int = 400) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_SPLIT.split(text):
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(sentence, max_chars))
        elif current and len(current) + 1 + len(sentence) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks
