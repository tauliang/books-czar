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
        if "mastery assessment designer" in system_prompt:
            return (
                '{ "title": "Mastery Quiz: Local Strategy", "questions": ['
                '{ "id": "q1", "prompt": "What should leaders use for strategy research?",'
                '"choices": ['
                '{"id": "A", "text": "A private RAG library with cited local context", "correct": true},'
                '{"id": "B", "text": "Uncited public guesses", "correct": false},'
                '{"id": "C", "text": "A spreadsheet with no sources", "correct": false},'
                '{"id": "D", "text": "Only memory from meetings", "correct": false}'
                '], "explanation": "The excerpt supports private RAG with citations.", "citations": ["S1"] },'
                '{ "id": "q2", "prompt": "What practice improves trust in answers?",'
                '"choices": ['
                '{"id": "A", "text": "Careful source citations", "correct": true},'
                '{"id": "B", "text": "Removing evidence", "correct": false},'
                '{"id": "C", "text": "Ignoring local books", "correct": false},'
                '{"id": "D", "text": "Avoiding review", "correct": false}'
                '], "explanation": "The excerpt emphasizes source citations.", "citations": ["S1"] },'
                '{ "id": "q3", "prompt": "What should executives prioritize?",'
                '"choices": ['
                '{"id": "A", "text": "Governed local evidence reuse", "correct": true},'
                '{"id": "B", "text": "Unmanaged leakage", "correct": false},'
                '{"id": "C", "text": "No measurement", "correct": false},'
                '{"id": "D", "text": "Discarding knowledge", "correct": false}'
                '], "explanation": "The excerpt points to governed local strategy research.", "citations": ["S1"] },'
                '{ "id": "q4", "prompt": "What makes the workflow local?",'
                '"choices": ['
                '{"id": "A", "text": "Indexed local content", "correct": true},'
                '{"id": "B", "text": "External-only search", "correct": false},'
                '{"id": "C", "text": "Anonymous web snippets", "correct": false},'
                '{"id": "D", "text": "No book storage", "correct": false}'
                '], "explanation": "The material is retrieved from indexed local content.", "citations": ["S1"] },'
                '{ "id": "q5", "prompt": "Why cite sources?",'
                '"choices": ['
                '{"id": "A", "text": "To verify claims against book excerpts", "correct": true},'
                '{"id": "B", "text": "To hide provenance", "correct": false},'
                '{"id": "C", "text": "To make answers longer", "correct": false},'
                '{"id": "D", "text": "To avoid accountability", "correct": false}'
                '], "explanation": "Citations connect claims to retrieved excerpts.", "citations": ["S1"] }'
                '] }'
            )
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


def test_quiz_api_creates_scores_and_exports_certificate(api_client, monkeypatch):
    import backend.storage as storage

    monkeypatch.setattr(storage, "LMStudioClient", FakeLMStudioClient)

    upload = api_client.post(
        "/api/books/upload",
        files={
            "files": (
                "mastery-strategy.txt",
                b"Executive leaders need private RAG strategy research with careful source citations.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 200
    indexed = api_client.post("/api/index", json={"book_ids": None})
    assert indexed.status_code == 200

    created = api_client.post("/api/quizzes", json={"book_ids": None, "question_count": 5})

    assert created.status_code == 200
    quiz = created.json()
    assert quiz["status"] == "complete"
    assert quiz["title"] == "Mastery Quiz: Local Strategy"
    assert len(quiz["questions"]) == 5
    assert "correct" not in quiz["questions"][0]["choices"][0]
    assert "exactly 4 choices" in FakeLMStudioClient.last_user_prompt
    assert "Exactly 1 choice must have correct=true" in FakeLMStudioClient.last_user_prompt

    fetched = api_client.get(f"/api/quizzes/{quiz['id']}")
    assert fetched.status_code == 200
    assert "correct" not in fetched.json()["questions"][0]["choices"][0]

    attempt = api_client.post(
        f"/api/quizzes/{quiz['id']}/attempts",
        json={
            "learner_name": "Ada Lovelace",
            "answers": {f"q{index}": "A" for index in range(1, 6)},
        },
    )
    assert attempt.status_code == 200
    attempt_payload = attempt.json()
    assert attempt_payload["score"] == 100.0
    assert attempt_payload["passed"] is True
    assert attempt_payload["results"][0]["correct_choice_id"] == "A"

    attempts = api_client.get(f"/api/quizzes/{quiz['id']}/attempts")
    assert attempts.status_code == 200
    assert attempts.json()[0]["id"] == attempt_payload["id"]

    certificate = api_client.get(f"/api/quiz-attempts/{attempt_payload['id']}/certificate")
    assert certificate.status_code == 200
    assert certificate.headers["content-type"] == "application/pdf"
    assert certificate.headers["content-disposition"].endswith(".pdf\"")
    assert certificate.content.startswith(b"%PDF")
