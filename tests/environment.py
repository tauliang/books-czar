from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


class FakeLMStudioClient:
    last_system_prompt = ""
    last_user_prompt = ""

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
                '{ "id": "q1", "prompt": "What should leaders use?", "choices": ['
                '{"id": "A", "text": "Cited local evidence", "correct": true},'
                '{"id": "B", "text": "Uncited guesses", "correct": false},'
                '{"id": "C", "text": "No sources", "correct": false},'
                '{"id": "D", "text": "Ad hoc memory", "correct": false}'
                '], "explanation": "The excerpt supports cited local evidence.", "citations": ["S1"] },'
                '{ "id": "q2", "prompt": "What should be measured?", "choices": ['
                '{"id": "A", "text": "Adoption goals", "correct": true},'
                '{"id": "B", "text": "Nothing", "correct": false},'
                '{"id": "C", "text": "Rumors", "correct": false},'
                '{"id": "D", "text": "Guesswork", "correct": false}'
                '], "explanation": "The excerpt mentions measurable adoption goals.", "citations": ["S1"] },'
                '{ "id": "q3", "prompt": "What reduces risk?", "choices": ['
                '{"id": "A", "text": "Governance controls", "correct": true},'
                '{"id": "B", "text": "Ignoring controls", "correct": false},'
                '{"id": "C", "text": "Deleting evidence", "correct": false},'
                '{"id": "D", "text": "Avoiding review", "correct": false}'
                '], "explanation": "Governance controls are named in the excerpt.", "citations": ["S1"] },'
                '{ "id": "q4", "prompt": "What should strategy align with?", "choices": ['
                '{"id": "A", "text": "Local evidence", "correct": true},'
                '{"id": "B", "text": "No context", "correct": false},'
                '{"id": "C", "text": "Unverified claims", "correct": false},'
                '{"id": "D", "text": "Random prompts", "correct": false}'
                '], "explanation": "The excerpt says strategy should align with local evidence.", "citations": ["S1"] },'
                '{ "id": "q5", "prompt": "What knowledge source is tested?", "choices": ['
                '{"id": "A", "text": "Indexed local books", "correct": true},'
                '{"id": "B", "text": "External posts only", "correct": false},'
                '{"id": "C", "text": "Unstored chats", "correct": false},'
                '{"id": "D", "text": "Empty notes", "correct": false}'
                '], "explanation": "The workflow uses indexed local books.", "citations": ["S1"] }'
                '] }'
            )
        if "Board Brief" in system_prompt:
            return (
                "## Executive Takeaway\n"
                "Executives should use cited local evidence for strategy decisions [S1].\n\n"
                "## Recommended 30/60/90 Day Actions\n"
                "- 30 days: Confirm priority indexed sources [S1].\n\n"
                "## Metrics to Watch\n"
                "- Adoption goal progress [S1]."
            )
        return "RAG answer based on retrieved local context [1]"


def before_scenario(context, _scenario):
    context.tempdir = tempfile.TemporaryDirectory()
    context.workspace = Path(context.tempdir.name)
    context.old_env = {
        key: os.environ.get(key)
        for key in (
            "BOOKWISE_DATA_DIR",
            "BOOKWISE_BOOKS_DIR",
            "LMSTUDIO_BASE_URL",
            "LMSTUDIO_CHAT_MODEL",
            "LMSTUDIO_EMBEDDING_MODEL",
        )
    }
    os.environ["BOOKWISE_DATA_DIR"] = str(context.workspace / "data")
    os.environ["BOOKWISE_BOOKS_DIR"] = str(context.workspace / "books")
    os.environ["LMSTUDIO_BASE_URL"] = "http://127.0.0.1:1234/v1"
    os.environ["LMSTUDIO_CHAT_MODEL"] = "test-chat"
    os.environ["LMSTUDIO_EMBEDDING_MODEL"] = "test-embedding"

    from backend.config import get_settings

    get_settings.cache_clear()

    import backend.main as main
    import backend.storage as storage

    context.original_main_lmstudio = main.LMStudioClient
    context.original_storage_lmstudio = storage.LMStudioClient
    main.LMStudioClient = FakeLMStudioClient
    storage.LMStudioClient = FakeLMStudioClient
    FakeLMStudioClient.last_system_prompt = ""
    FakeLMStudioClient.last_user_prompt = ""
    context.fake_lmstudio = FakeLMStudioClient

    context.client_manager = TestClient(main.app)
    context.client = context.client_manager.__enter__()


def after_scenario(context, _scenario):
    import backend.main as main
    import backend.storage as storage
    from backend.config import get_settings

    context.client_manager.__exit__(None, None, None)
    main.LMStudioClient = context.original_main_lmstudio
    storage.LMStudioClient = context.original_storage_lmstudio
    get_settings.cache_clear()

    for key, value in context.old_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    context.tempdir.cleanup()
