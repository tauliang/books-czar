from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT
from ebooklib import epub
from pypdf import PdfReader

from .chunking import TextSection, normalize_text


@dataclass(frozen=True)
class ParsedDocument:
    title: str | None
    author: str | None
    sections: list[TextSection]


SUPPORTED_EXTENSIONS = {".pdf", ".epub", ".txt", ".md", ".markdown", ".html", ".htm"}


def parse_document(path: Path) -> ParsedDocument:
    extension = path.suffix.lower()
    if extension == ".pdf":
        return _parse_pdf(path)
    if extension == ".epub":
        return _parse_epub(path)
    if extension in {".html", ".htm"}:
        return _parse_html(path)
    if extension in {".txt", ".md", ".markdown"}:
        return _parse_text(path)
    raise ValueError(f"Unsupported file type: {extension}")


def _parse_pdf(path: Path) -> ParsedDocument:
    reader = PdfReader(str(path))
    title = _clean_meta(reader.metadata.title if reader.metadata else None)
    author = _clean_meta(reader.metadata.author if reader.metadata else None)
    sections: list[TextSection] = []
    for index, page in enumerate(reader.pages, start=1):
        page_text = normalize_text(page.extract_text() or "")
        if page_text:
            sections.append(TextSection(location=f"page {index}", text=page_text))
    return ParsedDocument(title=title, author=author, sections=sections)


def _parse_epub(path: Path) -> ParsedDocument:
    try:
        book = epub.read_epub(str(path))
    except (BadZipFile, KeyError) as exc:
        raise ValueError("Could not read EPUB file") from exc

    title_values = book.get_metadata("DC", "title")
    author_values = book.get_metadata("DC", "creator")
    title = _clean_meta(title_values[0][0] if title_values else None)
    author = _clean_meta(author_values[0][0] if author_values else None)

    sections: list[TextSection] = []
    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = normalize_text(soup.get_text("\n"))
        if text:
            sections.append(TextSection(location=item.get_name(), text=text))
    return ParsedDocument(title=title, author=author, sections=sections)


def _parse_html(path: Path) -> ParsedDocument:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    title = _clean_meta(soup.title.string if soup.title else None)
    text = normalize_text(soup.get_text("\n"))
    return ParsedDocument(
        title=title,
        author=None,
        sections=[TextSection(location=path.name, text=text)] if text else [],
    )


def _parse_text(path: Path) -> ParsedDocument:
    text = normalize_text(path.read_text(encoding="utf-8", errors="ignore"))
    return ParsedDocument(
        title=path.stem.replace("_", " ").replace("-", " ").title(),
        author=None,
        sections=[TextSection(location=path.name, text=text)] if text else [],
    )


def _clean_meta(value: str | None) -> str | None:
    if not value:
        return None
    value = normalize_text(str(value))
    return value or None
