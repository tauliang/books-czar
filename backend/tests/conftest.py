from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def isolated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("BOOKWISE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BOOKWISE_BOOKS_DIR", str(tmp_path / "books"))
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("LMSTUDIO_CHAT_MODEL", "test-chat")
    monkeypatch.setenv("LMSTUDIO_EMBEDDING_MODEL", "test-embedding")

    from backend.config import get_settings

    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture()
def api_client(isolated_workspace: Path) -> Iterator[TestClient]:
    from backend.main import app

    with TestClient(app) as client:
        yield client
