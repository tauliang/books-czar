import type { AppSettings, Book, ChatResponse, Health, ModelCatalog } from "./types";

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
    })
};
