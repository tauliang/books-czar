from __future__ import annotations

from pathlib import Path

from backend.config import get_settings


class FakeLMStudioClient:
    last_user_prompt = ""
    last_system_prompt = ""

    def __init__(self, settings):
        self.settings = settings

    async def health(self) -> tuple[bool, str]:
        return True, "Fake LM Studio is reachable"

    async def models(self) -> list[str]:
        return ["text-embedding-test", "chat-test", "analysis-test"]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            embeddings.append(
                [
                    1.0 if "risk" in lowered else 0.0,
                    1.0 if "strategy" in lowered else 0.0,
                    min(len(text), 1000) / 1000,
                ]
            )
        return embeddings

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        self.__class__.last_system_prompt = system_prompt
        self.__class__.last_user_prompt = user_prompt
        if "Board Brief" in system_prompt:
            return (
                "## Executive Takeaway\n"
                "Leaders should use a private RAG library for faster strategy research [S1].\n\n"
                "## Recommended 30/60/90 Day Actions\n"
                "- 30 days: Identify indexed priority books [S1].\n\n"
                "## Metrics to Watch\n"
                "- Research cycle time [S1]."
            )
        return "RAG answer based on retrieved local context [1]"


def test_health_endpoint_uses_configured_lmstudio_client(api_client, monkeypatch):
    import backend.main as main

    monkeypatch.setattr(main, "LMStudioClient", FakeLMStudioClient)

    response = api_client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["lmstudio_ok"] is True
    assert payload["lmstudio_message"] == "Fake LM Studio is reachable"


def test_models_endpoint_returns_lmstudio_model_options(api_client, monkeypatch):
    import backend.main as main

    monkeypatch.setattr(main, "LMStudioClient", FakeLMStudioClient)

    response = api_client.get("/api/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["models"] == ["text-embedding-test", "chat-test", "analysis-test"]
    assert payload["chat_model"] == "test-chat"
    assert payload["embedding_model"] == "test-embedding"


def test_scan_local_books_endpoint_registers_books_folder(api_client):
    books_dir = get_settings().books_dir
    (books_dir / "strategy.txt").write_text("local AI strategy", encoding="utf-8")

    response = api_client.post("/api/books/scan-local")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scanned"] == 1
    assert payload["created"] == 1
    assert payload["skipped"] == 0

    books = api_client.get("/api/books").json()
    assert len(books) == 1
    assert books[0]["title"] == "Strategy"
    assert books[0]["source"] == "books_folder"


def test_upload_index_and_chat_follow_rag_flow(api_client, monkeypatch):
    import backend.storage as storage

    monkeypatch.setattr(storage, "LMStudioClient", FakeLMStudioClient)

    upload = api_client.post(
        "/api/books/upload",
        files={
            "files": (
                "risk-strategy.txt",
                b"The CDAO should measure lower data leakage risk and faster strategy research.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 200

    indexed = api_client.post("/api/index", json={"book_ids": None})
    assert indexed.status_code == 200
    assert indexed.json()["indexed"] == 1

    chat = api_client.post(
        "/api/chat",
        json={"message": "What risk should the CDAO measure?", "top_k": 3, "book_ids": None},
    )

    assert chat.status_code == 200
    payload = chat.json()
    assert payload["answer"] == "RAG answer based on retrieved local context [1]"
    assert payload["sources"]
    assert payload["sources"][0]["title"] == "Risk Strategy"
    assert "Excerpts:" in FakeLMStudioClient.last_user_prompt
    assert "lower data leakage risk" in FakeLMStudioClient.last_user_prompt
    assert "Cite sources inline" in FakeLMStudioClient.last_system_prompt


def test_settings_round_trip(api_client):
    response = api_client.put(
        "/api/settings",
        json={
            "lmstudio_base_url": "http://127.0.0.1:1234/v1",
            "chat_model": "test-chat-model",
            "embedding_model": "test-embedding-model",
            "chunk_size": 1200,
            "chunk_overlap": 120,
        },
    )

    assert response.status_code == 200
    assert response.json()["chat_model"] == "test-chat-model"
    assert api_client.get("/api/settings").json()["chunk_size"] == 1200


def test_synthesis_requires_indexed_books(api_client):
    response = api_client.post(
        "/api/syntheses",
        json={
            "objective": "Summarize our AI operating model",
            "audience": "c_suite",
            "lens": "operating_model",
            "book_ids": None,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Index one or more books before creating a synthesis."

    runs = api_client.get("/api/syntheses").json()
    assert runs[0]["status"] == "error"
    assert runs[0]["error"] == "Index one or more books before creating a synthesis."


def test_synthesis_api_creates_lists_reads_and_deletes_saved_brief(api_client, monkeypatch):
    import backend.storage as storage

    monkeypatch.setattr(storage, "LMStudioClient", FakeLMStudioClient)

    upload = api_client.post(
        "/api/books/upload",
        files={
            "files": (
                "executive-strategy.txt",
                b"Executive leaders need private RAG strategy research with careful source citations.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 200
    indexed = api_client.post("/api/index", json={"book_ids": None})
    assert indexed.status_code == 200

    created = api_client.post(
        "/api/syntheses",
        json={
            "objective": "Synthesize the executive AI strategy implications",
            "audience": "board",
            "lens": "strategy",
            "book_ids": None,
        },
    )

    assert created.status_code == 200
    payload = created.json()
    assert payload["status"] == "complete"
    assert "Executive Takeaway" in payload["markdown"]
    assert payload["sources"]
    assert payload["audience"] == "board"
    assert "Return exactly these sections:" in FakeLMStudioClient.last_user_prompt
    assert "one concise executive takeaway" in FakeLMStudioClient.last_user_prompt
    assert "3-6 measurable executive indicators" in FakeLMStudioClient.last_user_prompt
    assert "[S1]" in FakeLMStudioClient.last_user_prompt

    listed = api_client.get("/api/syntheses")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == payload["id"]

    fetched = api_client.get(f"/api/syntheses/{payload['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["markdown"] == payload["markdown"]

    exported = api_client.get(f"/api/syntheses/{payload['id']}/word")
    assert exported.status_code == 200
    assert exported.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert "books-czar-" in exported.headers["content-disposition"]
    assert exported.content.startswith(b"PK")

    deleted = api_client.delete(f"/api/syntheses/{payload['id']}")
    assert deleted.status_code == 200
    assert api_client.get(f"/api/syntheses/{payload['id']}").status_code == 404
