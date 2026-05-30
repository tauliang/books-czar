from __future__ import annotations

import json
import math
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from .chunking import chunk_sections
from .config import get_settings
from .database import db, dict_from_row, utc_now
from .lmstudio import LMStudioClient
from .manifest import ManifestItem, parse_manifest_bytes
from .parsers import SUPPORTED_EXTENSIONS, parse_document
from .schemas import AppSettings, BookOut, SourceOut
from .schemas import SynthesisRequest, SynthesisRunOut
from .synthesis import (
    build_synthesis_prompts,
    build_synthesis_retrieval_questions,
    dedupe_synthesis_sources,
)


def get_app_settings() -> AppSettings:
    values = _default_app_settings().model_dump()
    with db() as conn:
        for row in conn.execute("SELECT key, value FROM app_settings"):
            if row["key"] in values:
                values[row["key"]] = _coerce_setting(row["key"], row["value"])
    return AppSettings(**values)


def save_app_settings(settings: AppSettings) -> AppSettings:
    with db() as conn:
        for key, value in settings.model_dump().items():
            conn.execute(
                """
                INSERT INTO app_settings(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, str(value)),
            )
    return settings


def list_books() -> list[BookOut]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT b.*, COUNT(c.id) AS chunk_count
            FROM books b
            LEFT JOIN chunks c ON c.book_id = b.id
            GROUP BY b.id
            ORDER BY b.updated_at DESC
            """
        ).fetchall()
    return [BookOut(**dict_from_row(row)) for row in rows]


def get_book(book_id: str) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    return dict_from_row(row) if row else None


async def save_upload(file: UploadFile) -> BookOut:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {extension or 'unknown'}")
    book_id = uuid.uuid4().hex
    safe_name = _safe_filename(file.filename or f"book{extension}")
    target_dir = get_settings().library_dir / book_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name
    with target_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    now = utc_now()
    title = Path(safe_name).stem.replace("_", " ").replace("-", " ").title()
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
                None,
                "local_upload",
                None,
                safe_name,
                str(target_path),
                extension.removeprefix("."),
                "stored",
                None,
                now,
                now,
            ),
        )
    return next(book for book in list_books() if book.id == book_id)


def import_manifest(file_name: str, content: bytes) -> tuple[int, int, list[str]]:
    items = parse_manifest_bytes(file_name, content)
    created = 0
    skipped = 0
    notes: list[str] = []
    for item in items:
        if _manifest_item_exists(item):
            skipped += 1
            continue
        create_manifest_book(item)
        created += 1
    return created, skipped, notes


def scan_books_folder() -> tuple[str, int, int, int, list[str]]:
    settings = get_settings()
    books_dir = settings.books_dir.resolve()
    books_dir.mkdir(parents=True, exist_ok=True)
    existing_paths = _existing_file_paths()
    candidates = sorted(
        path
        for path in books_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    created = 0
    skipped = 0
    notes: list[str] = []
    now = utc_now()
    with db() as conn:
        for path in candidates:
            resolved = str(path.resolve())
            if resolved in existing_paths:
                skipped += 1
                continue
            relative = path.relative_to(books_dir)
            title = _title_from_file(path)
            conn.execute(
                """
                INSERT INTO books(
                    id, title, author, source, source_url, file_name, file_path,
                    file_format, status, note, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    title,
                    None,
                    "books_folder",
                    None,
                    path.name,
                    resolved,
                    path.suffix.lower().removeprefix("."),
                    "stored",
                    f"books/{relative.as_posix()}",
                    now,
                    now,
                ),
            )
            existing_paths.add(resolved)
            created += 1

    if not candidates:
        notes.append(f"No supported files found in {books_dir}")
    return str(books_dir), len(candidates), created, skipped, notes


def create_manifest_book(item: ManifestItem) -> str:
    now = utc_now()
    book_id = uuid.uuid4().hex
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
                item.title,
                item.author,
                "manifest",
                item.source_url or item.download_url,
                None,
                None,
                None,
                "wanted",
                None,
                now,
                now,
            ),
        )
    return book_id


async def attach_file_to_book(book_id: str, file: UploadFile) -> BookOut:
    book = get_book(book_id)
    if not book:
        raise ValueError("Book not found")
    extension = Path(file.filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {extension or 'unknown'}")
    safe_name = _safe_filename(file.filename or f"book{extension}")
    target_dir = get_settings().library_dir / book_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name
    with target_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    with db() as conn:
        conn.execute(
            """
            UPDATE books
            SET file_name = ?, file_path = ?, file_format = ?, status = ?,
                note = NULL, updated_at = ?
            WHERE id = ?
            """,
            (safe_name, str(target_path), extension.removeprefix("."), "stored", utc_now(), book_id),
        )
    return next(book for book in list_books() if book.id == book_id)


async def index_books(book_ids: list[str] | None = None) -> tuple[int, int, list[str]]:
    settings = get_app_settings()
    lmstudio = LMStudioClient(settings)
    books = _indexable_books(book_ids)
    indexed = 0
    failed = 0
    notes: list[str] = []
    for book in books:
        try:
            await _index_one_book(book, settings, lmstudio)
            indexed += 1
        except Exception as exc:  # noqa: BLE001 - per-book failure should not stop a batch.
            failed += 1
            notes.append(f"{book['title']}: {exc}")
            _update_book_status(book["id"], "error", str(exc))
    return indexed, failed, notes


async def retrieve_sources(
    message: str,
    top_k: int,
    book_ids: list[str] | None,
) -> list[SourceOut]:
    settings = get_app_settings()
    lmstudio = LMStudioClient(settings)
    query_embedding = (await lmstudio.embed_texts([message]))[0]
    rows = _load_embedded_chunks(book_ids)
    scored: list[SourceOut] = []
    for row in rows:
        score = _cosine_similarity(query_embedding, json.loads(row["embedding"]))
        scored.append(
            SourceOut(
                book_id=row["book_id"],
                title=row["title"],
                location=row["location"],
                excerpt=_excerpt(row["text"]),
                score=score,
            )
        )
    scored.sort(key=lambda source: source.score, reverse=True)
    return scored[:top_k]


async def answer_with_sources(message: str, top_k: int, book_ids: list[str] | None) -> tuple[str, list[SourceOut]]:
    settings = get_app_settings()
    lmstudio = LMStudioClient(settings)
    sources = await retrieve_sources(message, top_k, book_ids)
    if not sources:
        return "I could not find indexed passages to answer from. Index one or more books first.", []

    context_blocks = []
    for index, source in enumerate(sources, start=1):
        context_blocks.append(
            f"[{index}] {source.title} ({source.location or 'unknown location'})\n{source.excerpt}"
        )
    system_prompt = (
        "You are a local research assistant for a private book library. "
        "Answer from the provided excerpts when possible. Cite sources inline using bracket numbers. "
        "If the excerpts do not contain the answer, say what is missing instead of inventing it."
    )
    user_prompt = f"Question:\n{message}\n\nExcerpts:\n\n" + "\n\n".join(context_blocks)
    answer = await lmstudio.chat(system_prompt, user_prompt)
    return answer, sources


async def create_synthesis_run(request: SynthesisRequest) -> SynthesisRunOut:
    request = request.model_copy(update={"objective": request.objective.strip()})
    resolved_book_ids = _indexed_book_ids(request.book_ids)
    title = _synthesis_title(request.objective)
    run_id = _insert_synthesis_run(title, request, resolved_book_ids)
    try:
        sources = await _retrieve_synthesis_sources(request, resolved_book_ids)
        if not sources:
            raise ValueError("Index one or more books before creating a synthesis.")
        markdown = await _generate_synthesis_markdown(request, sources)
        _update_synthesis_run(run_id, "complete", markdown, sources, None)
    except Exception as exc:
        _update_synthesis_run(run_id, "error", "", [], str(exc))
        raise
    synthesis = get_synthesis_run(run_id)
    if synthesis is None:
        raise ValueError("Synthesis run could not be loaded")
    return synthesis


def list_synthesis_runs() -> list[SynthesisRunOut]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM synthesis_runs ORDER BY created_at DESC, title"
        ).fetchall()
    return [_synthesis_from_row(row) for row in rows]


def get_synthesis_run(run_id: str) -> SynthesisRunOut | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM synthesis_runs WHERE id = ?", (run_id,)).fetchone()
    return _synthesis_from_row(row) if row else None


def delete_synthesis_run(run_id: str) -> bool:
    with db() as conn:
        cursor = conn.execute("DELETE FROM synthesis_runs WHERE id = ?", (run_id,))
    return cursor.rowcount > 0


def counts() -> tuple[int, int]:
    with db() as conn:
        book_count = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    return int(book_count), int(chunk_count)


def delete_book(book_id: str) -> bool:
    book = get_book(book_id)
    if not book:
        return False
    with db() as conn:
        conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    file_path = book.get("file_path")
    if file_path:
        library_root = get_settings().library_dir.resolve()
        path = Path(file_path).resolve()
        if path.is_relative_to(library_root) and path.parent != library_root:
            shutil.rmtree(path.parent, ignore_errors=True)
    return True


def _manifest_item_exists(item: ManifestItem) -> bool:
    with db() as conn:
        if item.source_url or item.download_url:
            row = conn.execute(
                "SELECT 1 FROM books WHERE source_url IN (?, ?) LIMIT 1",
                (item.source_url, item.download_url),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM books WHERE lower(title) = lower(?) LIMIT 1",
                (item.title,),
            ).fetchone()
    return row is not None


def _existing_file_paths() -> set[str]:
    paths: set[str] = set()
    with db() as conn:
        rows = conn.execute("SELECT file_path FROM books WHERE file_path IS NOT NULL").fetchall()
    for row in rows:
        try:
            paths.add(str(Path(row["file_path"]).resolve()))
        except OSError:
            paths.add(row["file_path"])
    return paths


def _indexable_books(book_ids: list[str] | None) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = "WHERE file_path IS NOT NULL"
    if book_ids:
        placeholders = ",".join("?" for _ in book_ids)
        where += f" AND id IN ({placeholders})"
        params.extend(book_ids)
    with db() as conn:
        rows = conn.execute(f"SELECT * FROM books {where} ORDER BY title", params).fetchall()
    return [dict_from_row(row) for row in rows]


async def _index_one_book(
    book: dict[str, Any],
    settings: AppSettings,
    lmstudio: LMStudioClient,
) -> None:
    path = Path(book["file_path"])
    if not path.exists():
        raise ValueError("Local file is missing")
    _update_book_status(book["id"], "indexing", None)
    parsed = parse_document(path)
    chunks = chunk_sections(parsed.sections, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError("No extractable text found")

    if parsed.title or parsed.author:
        with db() as conn:
            conn.execute(
                """
                UPDATE books
                SET title = COALESCE(?, title), author = COALESCE(?, author), updated_at = ?
                WHERE id = ?
                """,
                (parsed.title, parsed.author, utc_now(), book["id"]),
            )

    with db() as conn:
        conn.execute("DELETE FROM chunks WHERE book_id = ?", (book["id"],))

    for offset in range(0, len(chunks), 24):
        batch = chunks[offset : offset + 24]
        embeddings = await lmstudio.embed_texts([chunk.text for chunk in batch])
        now = utc_now()
        with db() as conn:
            for index, (chunk, embedding) in enumerate(zip(batch, embeddings), start=offset):
                conn.execute(
                    """
                    INSERT INTO chunks(id, book_id, chunk_index, location, text, embedding, created_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        book["id"],
                        index,
                        chunk.location,
                        chunk.text,
                        json.dumps(embedding),
                        now,
                    ),
                )
    _update_book_status(book["id"], "indexed", f"Indexed {len(chunks)} chunks")


def _update_book_status(book_id: str, status: str, note: str | None) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE books SET status = ?, note = ?, updated_at = ? WHERE id = ?",
            (status, note, utc_now(), book_id),
        )


def _load_embedded_chunks(book_ids: list[str] | None) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if book_ids:
        placeholders = ",".join("?" for _ in book_ids)
        where = f"WHERE c.book_id IN ({placeholders})"
        params.extend(book_ids)
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT c.book_id, c.location, c.text, c.embedding, b.title
            FROM chunks c
            JOIN books b ON b.id = c.book_id
            {where}
            """,
            params,
        ).fetchall()
    return [dict_from_row(row) for row in rows]


async def _retrieve_synthesis_sources(
    request: SynthesisRequest,
    book_ids: list[str],
) -> list[SourceOut]:
    if not book_ids:
        return []
    collected: list[SourceOut] = []
    questions = build_synthesis_retrieval_questions(
        request.objective,
        request.audience,
        request.lens,
    )
    for question in questions:
        collected.extend(await retrieve_sources(question, 4, book_ids))
    return dedupe_synthesis_sources(collected)


async def _generate_synthesis_markdown(
    request: SynthesisRequest,
    sources: list[SourceOut],
) -> str:
    settings = get_app_settings()
    lmstudio = LMStudioClient(settings)
    system_prompt, user_prompt = build_synthesis_prompts(request, sources)
    return await lmstudio.chat(system_prompt, user_prompt)


def _indexed_book_ids(book_ids: list[str] | None) -> list[str]:
    params: list[Any] = []
    where = ""
    if book_ids is not None:
        if not book_ids:
            return []
        placeholders = ",".join("?" for _ in book_ids)
        where = f"WHERE b.id IN ({placeholders})"
        params.extend(book_ids)
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT b.id, b.title
            FROM books b
            JOIN chunks c ON c.book_id = b.id
            {where}
            ORDER BY b.title
            """,
            params,
        ).fetchall()
    return [row["id"] for row in rows]


def _insert_synthesis_run(
    title: str,
    request: SynthesisRequest,
    book_ids: list[str],
) -> str:
    run_id = uuid.uuid4().hex
    now = utc_now()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO synthesis_runs(
                id, title, objective, audience, lens, book_ids, status,
                markdown, sources, error, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                title,
                request.objective,
                request.audience,
                request.lens,
                json.dumps(book_ids),
                "running",
                "",
                "[]",
                None,
                now,
                now,
            ),
        )
    return run_id


def _update_synthesis_run(
    run_id: str,
    status: str,
    markdown: str,
    sources: list[SourceOut],
    error: str | None,
) -> None:
    with db() as conn:
        conn.execute(
            """
            UPDATE synthesis_runs
            SET status = ?, markdown = ?, sources = ?, error = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                markdown,
                json.dumps([source.model_dump() for source in sources]),
                error,
                utc_now(),
                run_id,
            ),
        )


def _synthesis_from_row(row: Any) -> SynthesisRunOut:
    values = dict_from_row(row)
    values["book_ids"] = json.loads(values["book_ids"] or "[]")
    values["sources"] = [
        SourceOut(**source)
        for source in json.loads(values["sources"] or "[]")
    ]
    return SynthesisRunOut(**values)


def _synthesis_title(objective: str) -> str:
    clean = re.sub(r"\s+", " ", objective).strip()
    if not clean:
        return "Executive Synthesis"
    return clean if len(clean) <= 72 else f"{clean[:72].rsplit(' ', 1)[0]}..."


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _excerpt(text: str, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else f"{text[:limit].rsplit(' ', 1)[0]}..."


def _safe_filename(file_name: str) -> str:
    stem = Path(file_name).stem or "book"
    suffix = Path(file_name).suffix.lower()
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-") or "book"
    return f"{stem[:120]}{suffix}"


def _title_from_file(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").title()


def _coerce_setting(key: str, value: str) -> int | str:
    if key in {"chunk_size", "chunk_overlap"}:
        return int(value)
    return value


def _default_app_settings() -> AppSettings:
    runtime = get_settings()
    return AppSettings(
        lmstudio_base_url=runtime.lmstudio_base_url,
        chat_model=runtime.lmstudio_chat_model,
        embedding_model=runtime.lmstudio_embedding_model,
    )
