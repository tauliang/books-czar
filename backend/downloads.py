from __future__ import annotations

import re
import uuid
from email.message import Message
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import get_settings
from .database import db, utc_now
from .parsers import SUPPORTED_EXTENSIONS
from .schemas import DirectDownloadItem
from .storage import list_books


CONTENT_TYPE_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/epub+zip": ".epub",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/html": ".html",
}


async def download_authorized_item(item: DirectDownloadItem) -> tuple[bool, str]:
    url = str(item.url)
    extension = _extension_from_url(url)
    settings = get_settings()
    max_bytes = settings.max_download_mb * 1024 * 1024
    book_id = uuid.uuid4().hex

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";")[0].lower()
                extension = extension or CONTENT_TYPE_EXTENSIONS.get(content_type)
                if extension not in SUPPORTED_EXTENSIONS:
                    return False, f"{item.title or url}: unsupported download format"

                file_name = _filename_from_headers(response.headers.get("content-disposition"))
                if not file_name:
                    file_name = _filename_from_url(url, extension)
                safe_name = _safe_filename(file_name)
                target_dir = settings.library_dir / book_id
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / safe_name

                total = 0
                with target_path.open("wb") as output:
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            target_path.unlink(missing_ok=True)
                            return False, f"{item.title or url}: exceeds {settings.max_download_mb} MB"
                        output.write(chunk)
    except Exception as exc:  # noqa: BLE001 - return a row-level download note.
        return False, f"{item.title or url}: {exc}"

    now = utc_now()
    title = item.title or Path(safe_name).stem.replace("_", " ").replace("-", " ").title()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO books(
                id, title, author, source, source_url, file_name, file_path,
                file_format, status, note, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                book_id,
                title,
                item.author,
                "direct_download",
                url,
                safe_name,
                str(target_path),
                extension.removeprefix("."),
                "stored",
                None,
                now,
                now,
            ),
        )
    return True, f"{title}: downloaded"


def latest_book_id() -> str | None:
    books = list_books()
    return books[0].id if books else None


def _extension_from_url(url: str) -> str | None:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in SUPPORTED_EXTENSIONS else None


def _filename_from_url(url: str, extension: str) -> str:
    name = Path(urlparse(url).path).name
    if not name:
        name = f"download{extension}"
    if not Path(name).suffix:
        name = f"{name}{extension}"
    return name


def _filename_from_headers(content_disposition: str | None) -> str | None:
    if not content_disposition:
        return None
    message = Message()
    message["content-disposition"] = content_disposition
    params = message.get_params(header="content-disposition")
    for key, value in params:
        if key.lower() == "filename" and value:
            return value
    return None


def _safe_filename(file_name: str) -> str:
    path = Path(file_name)
    suffix = path.suffix.lower()
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip(".-") or "download"
    return f"{stem[:120]}{suffix}"
