from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ManifestItem:
    title: str
    author: str | None
    source_url: str | None
    download_url: str | None


def parse_manifest_bytes(file_name: str, content: bytes) -> list[ManifestItem]:
    text = content.decode("utf-8-sig", errors="ignore").strip()
    if not text:
        return []
    suffix = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    if suffix == "json" or text[0] in "[{":
        return _parse_json(text)
    return _parse_csv_or_lines(text)


def _parse_json(text: str) -> list[ManifestItem]:
    raw = json.loads(text)
    if isinstance(raw, dict):
        raw_items = raw.get("books") or raw.get("items") or raw.get("titles") or []
    elif isinstance(raw, list):
        raw_items = raw
    else:
        raw_items = []

    items: list[ManifestItem] = []
    for entry in raw_items:
        if isinstance(entry, str):
            items.append(_from_values(title=entry, author=None, source_url=entry, download_url=None))
        elif isinstance(entry, dict):
            items.append(
                _from_values(
                    title=entry.get("title") or entry.get("name") or "",
                    author=entry.get("author") or entry.get("authors"),
                    source_url=entry.get("url") or entry.get("source_url"),
                    download_url=entry.get("download_url") or entry.get("file_url"),
                )
            )
    return [item for item in items if item.title or item.source_url or item.download_url]


def _parse_csv_or_lines(text: str) -> list[ManifestItem]:
    sample = text[:2048]
    has_header = "title" in sample.lower() or "url" in sample.lower()
    if "," in sample or "\t" in sample:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
        stream = io.StringIO(text)
        if has_header:
            rows = csv.DictReader(stream, dialect=dialect)
            return [
                _from_values(
                    title=row.get("title") or row.get("name") or "",
                    author=row.get("author") or row.get("authors"),
                    source_url=row.get("url") or row.get("source_url"),
                    download_url=row.get("download_url") or row.get("file_url"),
                )
                for row in rows
            ]
        rows = csv.reader(stream, dialect=dialect)
        return [
            _from_values(
                title=row[0] if row else "",
                author=row[1] if len(row) > 1 else None,
                source_url=row[2] if len(row) > 2 else None,
                download_url=row[3] if len(row) > 3 else None,
            )
            for row in rows
            if row
        ]

    return [
        _from_values(title=line, author=None, source_url=line, download_url=None)
        for line in text.splitlines()
        if line.strip()
    ]


def _from_values(
    title: str | None,
    author: str | list[str] | None,
    source_url: str | None,
    download_url: str | None,
) -> ManifestItem:
    clean_title = _clean(title)
    clean_source = _clean(source_url)
    clean_download = _clean(download_url)
    if _looks_like_url(clean_title) and not clean_source:
        clean_source = clean_title
        clean_title = ""
    if not clean_title and clean_source:
        clean_title = _title_from_url(clean_source)
    if not clean_title and clean_download:
        clean_title = _title_from_url(clean_download)
    if isinstance(author, list):
        clean_author = ", ".join(str(part) for part in author if part)
    else:
        clean_author = author
    return ManifestItem(
        title=_clean(clean_title) or "Untitled",
        author=_clean(clean_author),
        source_url=clean_source,
        download_url=clean_download,
    )


def _clean(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _looks_like_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _title_from_url(value: str) -> str:
    path = urlparse(value).path.strip("/")
    slug = path.split("/")[-1] if path else urlparse(value).netloc
    return slug.replace("-", " ").replace("_", " ").title()
