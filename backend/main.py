from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
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
    ModelListResponse,
    QuizAttemptOut,
    QuizAttemptRequest,
    QuizCreateRequest,
    QuizRunOut,
    SynthesisRequest,
    SynthesisRunOut,
)
from .storage import (
    answer_with_sources,
    attach_file_to_book,
    counts,
    create_quiz_attempt,
    create_quiz_run,
    create_synthesis_run,
    delete_book,
    delete_quiz_run,
    delete_synthesis_run,
    get_quiz_attempt,
    get_quiz_run,
    get_synthesis_run,
    get_app_settings,
    import_manifest,
    index_books,
    list_books,
    list_quiz_attempts,
    list_quiz_runs,
    list_synthesis_runs,
    save_app_settings,
    save_upload,
    scan_books_folder,
)
from .certificates import PDF_MIME_TYPE, build_certificate_pdf, certificate_filename
from .word_export import WORD_MIME_TYPE, build_synthesis_docx, word_filename


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
    expose_headers=["Content-Disposition"],
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


@app.get("/api/models", response_model=ModelListResponse)
async def read_models() -> ModelListResponse:
    settings = get_app_settings()
    try:
        models = await LMStudioClient(settings).models()
        return ModelListResponse(
            ok=True,
            message="LM Studio models loaded",
            models=models,
            chat_model=settings.chat_model,
            embedding_model=settings.embedding_model,
        )
    except Exception as exc:  # noqa: BLE001 - keep settings usable when LM Studio is offline.
        return ModelListResponse(
            ok=False,
            message=str(exc),
            models=[],
            chat_model=settings.chat_model,
            embedding_model=settings.embedding_model,
        )


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


@app.get("/api/syntheses", response_model=list[SynthesisRunOut])
async def read_syntheses() -> list[SynthesisRunOut]:
    return list_synthesis_runs()


@app.post("/api/syntheses", response_model=SynthesisRunOut)
async def create_synthesis(request: SynthesisRequest) -> SynthesisRunOut:
    try:
        return await create_synthesis_run(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - LM Studio errors should be readable in the UI.
        raise HTTPException(status_code=502, detail=f"Synthesis request failed: {exc}") from exc


@app.get("/api/syntheses/{run_id}", response_model=SynthesisRunOut)
async def read_synthesis(run_id: str) -> SynthesisRunOut:
    synthesis = get_synthesis_run(run_id)
    if synthesis is None:
        raise HTTPException(status_code=404, detail="Synthesis not found")
    return synthesis


@app.get("/api/syntheses/{run_id}/word")
async def export_synthesis_word(run_id: str) -> Response:
    synthesis = get_synthesis_run(run_id)
    if synthesis is None:
        raise HTTPException(status_code=404, detail="Synthesis not found")
    if synthesis.status != "complete" or not synthesis.markdown.strip():
        raise HTTPException(status_code=400, detail="Synthesis has no completed brief to export.")

    return Response(
        content=build_synthesis_docx(synthesis),
        media_type=WORD_MIME_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{word_filename(synthesis.title)}"'},
    )


@app.delete("/api/syntheses/{run_id}")
async def remove_synthesis(run_id: str):
    if not delete_synthesis_run(run_id):
        raise HTTPException(status_code=404, detail="Synthesis not found")
    return {"ok": True}


@app.get("/api/quizzes", response_model=list[QuizRunOut])
async def read_quizzes() -> list[QuizRunOut]:
    return list_quiz_runs()


@app.post("/api/quizzes", response_model=QuizRunOut)
async def create_quiz(request: QuizCreateRequest) -> QuizRunOut:
    try:
        return await create_quiz_run(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - LM Studio errors should be readable in the UI.
        raise HTTPException(status_code=502, detail=f"Quiz request failed: {exc}") from exc


@app.get("/api/quizzes/{quiz_id}", response_model=QuizRunOut)
async def read_quiz(quiz_id: str) -> QuizRunOut:
    quiz = get_quiz_run(quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


@app.delete("/api/quizzes/{quiz_id}")
async def remove_quiz(quiz_id: str):
    if not delete_quiz_run(quiz_id):
        raise HTTPException(status_code=404, detail="Quiz not found")
    return {"ok": True}


@app.post("/api/quizzes/{quiz_id}/attempts", response_model=QuizAttemptOut)
async def submit_quiz_attempt(quiz_id: str, request: QuizAttemptRequest) -> QuizAttemptOut:
    try:
        return create_quiz_attempt(quiz_id, request)
    except ValueError as exc:
        status = 404 if str(exc) == "Quiz not found" else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@app.get("/api/quizzes/{quiz_id}/attempts", response_model=list[QuizAttemptOut])
async def read_quiz_attempts(quiz_id: str) -> list[QuizAttemptOut]:
    if get_quiz_run(quiz_id) is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return list_quiz_attempts(quiz_id)


@app.get("/api/quiz-attempts/{attempt_id}/certificate")
async def export_quiz_certificate(attempt_id: str) -> Response:
    attempt = get_quiz_attempt(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    if not attempt.passed:
        raise HTTPException(status_code=400, detail="Certificate is available only for passed attempts.")
    quiz = get_quiz_run(attempt.quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return Response(
        content=build_certificate_pdf(quiz, attempt),
        media_type=PDF_MIME_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{certificate_filename(attempt.learner_name)}"',
        },
    )
