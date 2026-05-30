import type {
  AppSettings,
  Book,
  ChatResponse,
  Health,
  ModelCatalog,
  QuizAttempt,
  QuizAttemptRequest,
  QuizCreateRequest,
  QuizRun,
  SynthesisRequest,
  SynthesisRun
} from "./types";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: options.body instanceof FormData ? options.headers : {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    }
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail ?? detail;
    } catch {
      // Ignore non-JSON error payloads.
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json() as Promise<T>;
}

async function requestDownload(path: string, fallbackFilename: string): Promise<void> {
  const response = await fetch(path);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail ?? detail;
    } catch {
      // Ignore non-JSON error payloads.
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  const blob = await response.blob();
  const filename = filenameFromDisposition(response.headers.get("Content-Disposition"), fallbackFilename);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function filenameFromDisposition(disposition: string | null, fallbackFilename: string): string {
  const utfMatch = disposition?.match(/filename\*=UTF-8''([^;]+)/i);
  if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1]);
  const plainMatch = disposition?.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] ?? fallbackFilename;
}

export const api = {
  health: () => request<Health>("/api/health"),
  settings: () => request<AppSettings>("/api/settings"),
  models: () => request<ModelCatalog>("/api/models"),
  saveSettings: (settings: AppSettings) =>
    request<AppSettings>("/api/settings", { method: "PUT", body: JSON.stringify(settings) }),
  books: () => request<Book[]>("/api/books"),
  uploadBooks: (files: FileList) => {
    const form = new FormData();
    Array.from(files).forEach((file) => form.append("files", file));
    return request<{ uploaded: Book[] }>("/api/books/upload", { method: "POST", body: form });
  },
  attachFile: (bookId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Book>(`/api/books/${bookId}/file`, { method: "POST", body: form });
  },
  uploadManifest: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ created: number; skipped: number; notes: string[] }>("/api/books/manifest", {
      method: "POST",
      body: form
    });
  },
  scanBooksFolder: () =>
    request<{ books_dir: string; scanned: number; created: number; skipped: number; notes: string[] }>(
      "/api/books/scan-local",
      { method: "POST" }
    ),
  directDownload: (items: Array<{ title?: string; url: string }>) =>
    request<{ results: Array<{ ok: boolean; note: string }> }>("/api/books/download", {
      method: "POST",
      body: JSON.stringify({ confirm_authorized: true, items })
    }),
  indexBooks: (bookIds: string[] | null) =>
    request<{ indexed: number; failed: number; notes: string[] }>("/api/index", {
      method: "POST",
      body: JSON.stringify({ book_ids: bookIds })
    }),
  deleteBook: (bookId: string) => request<{ ok: boolean }>(`/api/books/${bookId}`, { method: "DELETE" }),
  chat: (message: string, bookIds: string[] | null, topK = 6) =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, book_ids: bookIds, top_k: topK })
    }),
  syntheses: () => request<SynthesisRun[]>("/api/syntheses"),
  synthesis: (id: string) => request<SynthesisRun>(`/api/syntheses/${id}`),
  createSynthesis: (payload: SynthesisRequest) =>
    request<SynthesisRun>("/api/syntheses", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  exportSynthesisWord: (id: string) =>
    requestDownload(`/api/syntheses/${id}/word`, "books-czar-board-brief.docx"),
  deleteSynthesis: (id: string) =>
    request<{ ok: boolean }>(`/api/syntheses/${id}`, { method: "DELETE" }),
  quizzes: () => request<QuizRun[]>("/api/quizzes"),
  quiz: (id: string) => request<QuizRun>(`/api/quizzes/${id}`),
  createQuiz: (payload: QuizCreateRequest) =>
    request<QuizRun>("/api/quizzes", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deleteQuiz: (id: string) =>
    request<{ ok: boolean }>(`/api/quizzes/${id}`, { method: "DELETE" }),
  quizAttempts: (quizId: string) => request<QuizAttempt[]>(`/api/quizzes/${quizId}/attempts`),
  submitQuizAttempt: (quizId: string, payload: QuizAttemptRequest) =>
    request<QuizAttempt>(`/api/quizzes/${quizId}/attempts`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  exportCertificate: (attemptId: string) =>
    requestDownload(`/api/quiz-attempts/${attemptId}/certificate`, "books-czar-certificate.pdf")
};
