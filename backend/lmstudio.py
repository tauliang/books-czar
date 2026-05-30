from __future__ import annotations

import httpx

from .schemas import AppSettings


class LMStudioClient:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.base_url = settings.lmstudio_base_url.rstrip("/")

    async def health(self) -> tuple[bool, str]:
        try:
            await self.models()
            return True, "LM Studio API is reachable"
        except Exception as exc:  # noqa: BLE001 - surface concise diagnostics to UI.
            return False, str(exc)

    async def models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{self.base_url}/models")
            response.raise_for_status()
            payload = response.json()
        return [row["id"] for row in payload.get("data", []) if "id" in row]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                json={"model": self.settings.embedding_model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()
        rows = sorted(payload["data"], key=lambda row: row.get("index", 0))
        return [row["embedding"] for row in rows]

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        model = await self._chat_model()
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            payload = response.json()
        return payload["choices"][0]["message"]["content"]

    async def _chat_model(self) -> str:
        if self.settings.chat_model and self.settings.chat_model != "local-model":
            return self.settings.chat_model
        models = await self.models()
        for model in models:
            lowered = model.lower()
            if "embed" not in lowered and "embedding" not in lowered:
                return model
        return self.settings.chat_model
