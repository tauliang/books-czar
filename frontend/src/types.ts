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

export interface ModelCatalog {
  ok: boolean;
  message: string;
  models: string[];
  chat_model: string;
  embedding_model: string;
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

export type SynthesisAudience = "board" | "c_suite" | "cdao_leadership" | "technical_leaders";
export type SynthesisLens =
  | "all"
  | "strategy"
  | "risk_governance"
  | "operating_model"
  | "investment"
  | "talent_change";

export interface SynthesisRequest {
  objective: string;
  audience: SynthesisAudience;
  lens: SynthesisLens;
  book_ids: string[] | null;
}

export interface SynthesisRun {
  id: string;
  title: string;
  objective: string;
  audience: SynthesisAudience;
  lens: SynthesisLens;
  book_ids: string[];
  status: string;
  markdown: string;
  sources: Source[];
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuizCreateRequest {
  book_ids: string[] | null;
  question_count: 5 | 10 | 15 | 20;
}

export interface QuizChoice {
  id: string;
  text: string;
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  choices: QuizChoice[];
  citations: string[];
}

export interface QuizRun {
  id: string;
  title: string;
  book_ids: string[];
  question_count: number;
  passing_score: number;
  status: string;
  questions: QuizQuestion[];
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuizAttemptRequest {
  learner_name: string;
  answers: Record<string, string>;
}

export interface QuizQuestionResult {
  question_id: string;
  prompt: string;
  choices: QuizChoice[];
  selected_choice_id?: string | null;
  correct_choice_id: string;
  correct: boolean;
  explanation: string;
  citations: string[];
}

export interface QuizAttempt {
  id: string;
  quiz_id: string;
  learner_name: string;
  answers: Record<string, string>;
  score: number;
  passed: boolean;
  results: QuizQuestionResult[];
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}
