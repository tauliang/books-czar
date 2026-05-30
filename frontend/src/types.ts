export type BookStatus = "wanted" | "needs_file" | "stored" | "indexing" | "indexed" | "error";

export interface Book {
  id: string;
  title: string;
  author?: string | null;
  source: string;
  source_url?: string | null;
  file_name?: string | null;
  file_format?: string | null;
  status: BookStatus | string;
  note?: string | null;
  created_at: string;
  updated_at: string;
  chunk_count: number;
}

export interface AppSettings {
  lmstudio_base_url: string;
  chat_model: string;
  embedding_model: string;
  chunk_size: number;
  chunk_overlap: number;
}

export interface Health {
  ok: boolean;
  lmstudio_ok: boolean;
  lmstudio_message: string;
  book_count: number;
  chunk_count: number;
}

export interface Source {
  book_id: string;
  title: string;
  location?: string | null;
  excerpt: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}
