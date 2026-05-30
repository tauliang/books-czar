from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class AppSettings(BaseModel):
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    chat_model: str = "local-model"
    embedding_model: str = "text-embedding-nomic-embed-text-v1.5"
    chunk_size: int = Field(default=1800, ge=500, le=5000)
    chunk_overlap: int = Field(default=240, ge=0, le=1000)


class BookOut(BaseModel):
    id: str
    title: str
    author: str | None = None
    source: str
    source_url: str | None = None
    file_name: str | None = None
    file_format: str | None = None
    status: str
    note: str | None = None
    created_at: str
    updated_at: str
    chunk_count: int = 0


class ManifestImportResult(BaseModel):
    created: int
    skipped: int
    notes: list[str] = []


class LocalScanResult(BaseModel):
    books_dir: str
    scanned: int
    created: int
    skipped: int
    notes: list[str] = []


class DirectDownloadItem(BaseModel):
    title: str | None = None
    author: str | None = None
    url: HttpUrl


class DirectDownloadRequest(BaseModel):
    confirm_authorized: bool = False
    items: list[DirectDownloadItem]


class IndexRequest(BaseModel):
    book_ids: list[str] | None = None


class IndexResult(BaseModel):
    indexed: int = 0
    failed: int = 0
    notes: list[str] = []


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    top_k: int = Field(default=6, ge=1, le=12)
    book_ids: list[str] | None = None


class SourceOut(BaseModel):
    book_id: str
    title: str
    location: str | None = None
    excerpt: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut]


class HealthResponse(BaseModel):
    ok: bool
    lmstudio_ok: bool
    lmstudio_message: str
    book_count: int
    chunk_count: int


class ModelListResponse(BaseModel):
    ok: bool
    message: str
    models: list[str]
    chat_model: str
    embedding_model: str
