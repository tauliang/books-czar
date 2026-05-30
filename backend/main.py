from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .downloads import download_authorized_item
from .lmstudio import LMStudioClient
from .schemas import (
    AppSettings,
    ChatRequest,
    ChatResponse,
    DirectDownloadRequest,
    HealthResponse,
    IndexRequest,
    IndexResult,
    LocalScanResult,
    ManifestImportResult,
)
from .storage import (
    answer_with_sources,
    attach_file_to_book,
    counts,
    delete_book,
    get_app_settings,
    import_manifest,
    index_books,
    list_books,
    save_app_settings,
    save_upload,
    scan_books_folder,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Books Czar API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    book_count, chunk_count = counts()
    lmstudio_ok, lmstudio_message = await LMStudioClient(get_app_settings()).health()
    return HealthResponse(
        ok=True,
        lmstudio_ok=lmstudio_ok,
        lmstudio_message=lmstudio_message,
        book_count=book_count,
        chunk_count=chunk_count,
    )


@app.get("/api/settings", response_model=AppSettings)
async def read_settings() -> AppSettings:
    return get_app_settings()


@app.put("/api/settings", response_model=AppSettings)
async def update_settings(settings: AppSettings) -> AppSettings:
    return save_app_settings(settings)


@app.get("/api/books")
async def read_books():
    return list_books()


@app.post("/api/books/upload")
async def upload_books(files: list[UploadFile] = File(...)):
    uploaded = []
    for file in files:
        try:
            uploaded.append(await save_upload(file))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"uploaded": uploaded}


@app.post("/api/books/{book_id}/file")
async def attach_book_file(book_id: str, file: UploadFile = File(...)):
    try:
        return await attach_file_to_book(book_id, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/books/manifest", response_model=ManifestImportResult)
async def upload_manifest(file: UploadFile = File(...)) -> ManifestImportResult:
    content = await file.read()
    try:
        created, skipped, notes = import_manifest(file.filename or "manifest.csv", content)
    except Exception as exc:  # noqa: BLE001 - parse errors should be user-visible.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ManifestImportResult(created=created, skipped=skipped, notes=notes)


@app.post("/api/books/scan-local", response_model=LocalScanResult)
async def scan_local_books() -> LocalScanResult:
    books_dir, scanned, created, skipped, notes = scan_books_folder()
    return LocalScanResult(
        books_dir=books_dir,
        scanned=scanned,
        created=created,
        skipped=skipped,
        notes=notes,
    )


@app.post("/api/books/download")
async def download_books(request: DirectDownloadRequest):
    if not request.confirm_authorized:
        raise HTTPException(
            status_code=400,
            detail="Confirm that each direct URL is authorized for local download.",
        )
    results = []
    for item in request.items:
        ok, note = await download_authorized_item(item)
        results.append({"ok": ok, "note": note})
    return {"results": results}


@app.delete("/api/books/{book_id}")
async def remove_book(book_id: str):
    if not delete_book(book_id):
        raise HTTPException(status_code=404, detail="Book not found")
    return {"ok": True}


@app.post("/api/index", response_model=IndexResult)
async def index_library(request: IndexRequest) -> IndexResult:
    indexed, failed, notes = await index_books(request.book_ids)
    return IndexResult(indexed=indexed, failed=failed, notes=notes)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        answer, sources = await answer_with_sources(request.message, request.top_k, request.book_ids)
    except Exception as exc:  # noqa: BLE001 - LM Studio errors should be readable in the UI.
        raise HTTPException(status_code=502, detail=f"LM Studio request failed: {exc}") from exc
    return ChatResponse(answer=answer, sources=sources)
