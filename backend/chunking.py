from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TextSection:
    location: str
    text: str


@dataclass(frozen=True)
class TextChunk:
    location: str
    text: str


_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANK_RE.sub("\n\n", text)
    return text.strip()


def chunk_sections(
    sections: list[TextSection],
    chunk_size: int = 1800,
    chunk_overlap: int = 240,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for section in sections:
        text = normalize_text(section.text)
        if not text:
            continue
        for part in _split_text(text, chunk_size, chunk_overlap):
            chunks.append(TextChunk(location=section.location, text=part))
    return chunks


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        hard_end = min(start + chunk_size, len(text))
        end = hard_end
        if hard_end < len(text):
            search_start = start + int(chunk_size * 0.55)
            paragraph_break = text.rfind("\n\n", search_start, hard_end)
            sentence_break = text.rfind(". ", search_start, hard_end)
            newline_break = text.rfind("\n", search_start, hard_end)
            end = max(paragraph_break, sentence_break + 1, newline_break)
            if end <= start:
                end = hard_end

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        next_start = max(0, end - chunk_overlap)
        start = next_start if next_start > start else end
    return chunks
