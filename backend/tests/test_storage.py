from __future__ import annotations

from pathlib import Path

from backend.config import get_settings
from backend.database import init_db
from backend.storage import delete_book, list_books, scan_books_folder


def test_scan_books_folder_registers_supported_files_once(isolated_workspace: Path):
    init_db()
    books_dir = get_settings().books_dir
    nested = books_dir / "leadership"
    nested.mkdir(parents=True)
    (nested / "ai-strategy.md").write_text("AI strategy and operating model", encoding="utf-8")
    (nested / "ignore.png").write_text("not a book", encoding="utf-8")

    _, scanned, created, skipped, notes = scan_books_folder()
    assert scanned == 1
    assert created == 1
    assert skipped == 0
    assert notes == []

    _, scanned_again, created_again, skipped_again, _ = scan_books_folder()
    assert scanned_again == 1
    assert created_again == 0
    assert skipped_again == 1

    books = list_books()
    assert len(books) == 1
    assert books[0].source == "books_folder"
    assert books[0].file_format == "md"


def test_delete_scanned_book_does_not_remove_source_file(isolated_workspace: Path):
    init_db()
    source_file = get_settings().books_dir / "platforms.txt"
    source_file.write_text("platform architecture", encoding="utf-8")

    scan_books_folder()
    book = list_books()[0]

    assert delete_book(book.id)
    assert source_file.exists()
    assert list_books() == []
