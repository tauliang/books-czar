import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  Cpu,
  Database,
  Download,
  FileText,
  FolderSearch,
  History,
  Library,
  Link,
  Loader2,
  MessageSquare,
  RefreshCw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Trash2,
  Upload
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { parseBriefMarkdown, presentableLines } from "./briefParser";
import type {
  AppSettings,
  Book,
  ChatMessage,
  Health,
  ModelCatalog,
  QuizAttempt,
  QuizRun,
  SynthesisAudience,
  SynthesisLens,
  SynthesisRun
} from "./types";

type Panel = "library" | "ask" | "import" | "synthesis" | "mastery" | "settings";

interface SynthesisFormState {
  objective: string;
  audience: SynthesisAudience;
  lens: SynthesisLens;
}

const emptySettings: AppSettings = {
  lmstudio_base_url: "http://127.0.0.1:1234/v1",
  chat_model: "local-model",
  embedding_model: "text-embedding-nomic-embed-text-v1.5",
  chunk_size: 1800,
  chunk_overlap: 240
};

const emptyModelCatalog: ModelCatalog = {
  ok: false,
  message: "Models not loaded",
  models: [],
  chat_model: emptySettings.chat_model,
  embedding_model: emptySettings.embedding_model
};

export default function App() {
  const [books, setBooks] = useState<Book[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [modelCatalog, setModelCatalog] = useState<ModelCatalog>(emptyModelCatalog);
  const [settings, setSettings] = useState<AppSettings>(emptySettings);
  const [syntheses, setSyntheses] = useState<SynthesisRun[]>([]);
  const [activeSynthesis, setActiveSynthesis] = useState<SynthesisRun | null>(null);
  const [quizzes, setQuizzes] = useState<QuizRun[]>([]);
  const [activeQuiz, setActiveQuiz] = useState<QuizRun | null>(null);
  const [quizAttempts, setQuizAttempts] = useState<QuizAttempt[]>([]);
  const [activeAttempt, setActiveAttempt] = useState<QuizAttempt | null>(null);
  const [learnerName, setLearnerName] = useState("");
  const [questionCount, setQuestionCount] = useState<5 | 10 | 15 | 20>(10);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [activeQuestionIndex, setActiveQuestionIndex] = useState(0);
  const [synthesisForm, setSynthesisForm] = useState<SynthesisFormState>({
    objective: "",
    audience: "c_suite",
    lens: "all"
  });
  const [panel, setPanel] = useState<Panel>(initialPanel);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [directUrls, setDirectUrls] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const uploadRef = useRef<HTMLInputElement | null>(null);
  const manifestRef = useRef<HTMLInputElement | null>(null);

  const selectedBooks = useMemo(
    () => books.filter((book) => selectedIds.includes(book.id)),
    [books, selectedIds]
  );
  const chatModelChoices = useMemo(
    () => withCurrentModel(["local-model", ...modelCatalog.models], settings.chat_model),
    [modelCatalog.models, settings.chat_model]
  );
  const embeddingModelChoices = useMemo(
    () => withCurrentModel(modelCatalog.models, settings.embedding_model),
    [modelCatalog.models, settings.embedding_model]
  );
  const indexedBooks = books.filter((book) => book.status === "indexed").length;
  const storedBooks = books.filter((book) => book.file_name).length;
  const selectedIndexedIds = useMemo(
    () =>
      selectedBooks
        .filter((book) => book.status === "indexed")
        .map((book) => book.id),
    [selectedBooks]
  );
  const synthesisScopeCount = selectedIds.length ? selectedIndexedIds.length : indexedBooks;
  const masteryScopeCount = selectedIds.length ? selectedIndexedIds.length : indexedBooks;

  useEffect(() => {
    void refreshAll();
  }, []);

  useEffect(() => {
    if (!activeSynthesis || synthesisForm.objective.trim()) return;
    setSynthesisForm({
      objective: activeSynthesis.objective,
      audience: activeSynthesis.audience,
      lens: activeSynthesis.lens
    });
  }, [activeSynthesis, synthesisForm.objective]);

  useEffect(() => {
    if (!activeQuiz) {
      setQuizAttempts([]);
      return;
    }
    void api.quizAttempts(activeQuiz.id)
      .then((attempts) => {
        setQuizAttempts(attempts);
        setActiveAttempt((current) =>
          current ? attempts.find((attempt) => attempt.id === current.id) ?? current : attempts[0] ?? null
        );
        if (attempts[0] && !learnerName.trim()) {
          setLearnerName(attempts[0].learner_name);
        }
        if (questionCountOptions.includes(activeQuiz.question_count as 5 | 10 | 15 | 20)) {
          setQuestionCount(activeQuiz.question_count as 5 | 10 | 15 | 20);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [activeQuiz?.id]);

  async function refreshAll() {
    setError(null);
    const [bookRows, healthRow, settingRow, modelRows, synthesisRows, quizRows] = await Promise.all([
      api.books(),
      api.health(),
      api.settings(),
      api.models(),
      api.syntheses(),
      api.quizzes()
    ]);
    setBooks(bookRows);
    setHealth(healthRow);
    setSettings(settingRow);
    setModelCatalog(modelRows);
    setSyntheses(synthesisRows);
    setQuizzes(quizRows);
    setActiveSynthesis((current) =>
      current ? synthesisRows.find((run) => run.id === current.id) ?? synthesisRows[0] ?? null : synthesisRows[0] ?? null
    );
    setActiveQuiz((current) =>
      current ? quizRows.find((run) => run.id === current.id) ?? quizRows[0] ?? null : quizRows[0] ?? null
    );
  }

  async function runTask(label: string, task: () => Promise<void>) {
    setBusy(label);
    setError(null);
    setNotice(null);
    try {
      await task();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleBookUpload(files: FileList | null) {
    if (!files?.length) return;
    await runTask("uploading", async () => {
      const result = await api.uploadBooks(files);
      setNotice(`${result.uploaded.length} file${result.uploaded.length === 1 ? "" : "s"} imported`);
      await refreshAll();
    });
    if (uploadRef.current) uploadRef.current.value = "";
  }

  async function handleManifestUpload(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    await runTask("manifest", async () => {
      const result = await api.uploadManifest(file);
      const notes = result.notes.length ? ` ${result.notes.slice(0, 2).join(" ")}` : "";
      setNotice(`${result.created} queued, ${result.skipped} skipped.${notes}`);
      await refreshAll();
      setPanel("library");
    });
    if (manifestRef.current) manifestRef.current.value = "";
  }

  async function handleScanBooksFolder() {
    await runTask("scanning", async () => {
      const result = await api.scanBooksFolder();
      const notes = result.notes.length ? ` ${result.notes.join(" ")}` : "";
      setNotice(
        `${result.created} added, ${result.skipped} skipped from ${result.scanned} supported files in ${result.books_dir}.${notes}`
      );
      await refreshAll();
      setPanel("library");
    });
  }

  async function handleAttachFile(bookId: string, file: File | null) {
    if (!file) return;
    await runTask("attaching", async () => {
      await api.attachFile(bookId, file);
      setNotice("File attached");
      await refreshAll();
    });
  }

  async function handleDirectDownload() {
    const items = parseDirectUrls(directUrls);
    if (!items.length) return;
    await runTask("downloading", async () => {
      const result = await api.directDownload(items);
      setNotice(result.results.map((row) => row.note).join(" "));
      await refreshAll();
    });
  }

  async function handleIndex(bookIds: string[] | null) {
    await runTask("indexing", async () => {
      const result = await api.indexBooks(bookIds);
      const note = result.notes.length ? ` ${result.notes.join(" ")}` : "";
      setNotice(`${result.indexed} indexed, ${result.failed} failed.${note}`);
      await refreshAll();
    });
  }

  async function handleDelete(bookId: string) {
    await runTask("deleting", async () => {
      await api.deleteBook(bookId);
      setSelectedIds((ids) => ids.filter((id) => id !== bookId));
      await refreshAll();
    });
  }

  async function handleSaveSettings(event: FormEvent) {
    event.preventDefault();
    await runTask("settings", async () => {
      const saved = await api.saveSettings(settings);
      setSettings(saved);
      setNotice("Settings saved");
      await refreshAll();
    });
  }

  async function handleCreateSynthesis(event: FormEvent) {
    event.preventDefault();
    const objective = synthesisForm.objective.trim();
    if (!objective) return;
    await runTask("synthesizing", async () => {
      const synthesis = await api.createSynthesis({
        objective,
        audience: synthesisForm.audience,
        lens: synthesisForm.lens,
        book_ids: selectedIds.length ? selectedIndexedIds : null
      });
      setActiveSynthesis(synthesis);
      setSyntheses((current) => [synthesis, ...current.filter((run) => run.id !== synthesis.id)]);
      setNotice("Synthesis saved");
      await refreshAll();
    });
  }

  async function handleOpenSynthesis(runId: string) {
    await runTask("loading synthesis", async () => {
      const synthesis = await api.synthesis(runId);
      setActiveSynthesis(synthesis);
    });
  }

  async function handleDeleteSynthesis(runId: string) {
    await runTask("deleting synthesis", async () => {
      await api.deleteSynthesis(runId);
      setSyntheses((current) => {
        const remaining = current.filter((run) => run.id !== runId);
        setActiveSynthesis((active) =>
          active?.id === runId ? remaining[0] ?? null : active
        );
        return remaining;
      });
      await refreshAll();
    });
  }

  async function handleExportSynthesis(run: SynthesisRun) {
    await runTask("exporting Word", async () => {
      await api.exportSynthesisWord(run.id);
      setNotice("Word brief downloaded");
    });
  }

  async function handleCreateQuiz(event: FormEvent) {
    event.preventDefault();
    await runTask("generating quiz", async () => {
      const quiz = await api.createQuiz({
        question_count: questionCount,
        book_ids: selectedIds.length ? selectedIndexedIds : null
      });
      setActiveQuiz(quiz);
      setQuizzes((current) => [quiz, ...current.filter((run) => run.id !== quiz.id)]);
      setQuizAnswers({});
      setActiveAttempt(null);
      setActiveQuestionIndex(0);
      setNotice("Mastery quiz saved");
      await refreshAll();
    });
  }

  async function handleOpenQuiz(quizId: string) {
    await runTask("loading quiz", async () => {
      const quiz = await api.quiz(quizId);
      setActiveQuiz(quiz);
      setQuizAnswers({});
      setActiveAttempt(null);
      setActiveQuestionIndex(0);
      const attempts = await api.quizAttempts(quizId);
      setQuizAttempts(attempts);
      setActiveAttempt(attempts[0] ?? null);
    });
  }

  async function handleDeleteQuiz(quizId: string) {
    await runTask("deleting quiz", async () => {
      await api.deleteQuiz(quizId);
      setQuizzes((current) => {
        const remaining = current.filter((run) => run.id !== quizId);
        setActiveQuiz((active) => (active?.id === quizId ? remaining[0] ?? null : active));
        return remaining;
      });
      setActiveAttempt(null);
      setQuizAnswers({});
      await refreshAll();
    });
  }

  async function handleSubmitQuiz() {
    if (!activeQuiz || !learnerName.trim()) return;
    await runTask("scoring quiz", async () => {
      const attempt = await api.submitQuizAttempt(activeQuiz.id, {
        learner_name: learnerName.trim(),
        answers: quizAnswers
      });
      setActiveAttempt(attempt);
      setQuizAttempts((current) => [attempt, ...current.filter((row) => row.id !== attempt.id)]);
      setNotice(attempt.passed ? "Mastery achieved" : "Attempt saved");
    });
  }

  async function handleExportCertificate(attempt: QuizAttempt) {
    await runTask("exporting certificate", async () => {
      await api.exportCertificate(attempt.id);
      setNotice("Certificate downloaded");
    });
  }

  async function handleChat(event: FormEvent) {
    event.preventDefault();
    const text = query.trim();
    if (!text) return;
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text };
    setMessages((current) => [...current, userMessage]);
    setQuery("");
    await runTask("chat", async () => {
      const response = await api.chat(text, selectedIds.length ? selectedIds : null);
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.answer,
        sources: response.sources
      };
      setMessages((current) => [...current, assistantMessage]);
    });
  }

  function toggleBook(bookId: string) {
    setSelectedIds((ids) =>
      ids.includes(bookId) ? ids.filter((id) => id !== bookId) : [...ids, bookId]
    );
  }


  function openPanel(nextPanel: Panel) {
    window.location.hash = nextPanel === "library" ? "" : nextPanel;
    setPanel(nextPanel);
  }

  const busyLabel = busy ? busy[0].toUpperCase() + busy.slice(1) : null;

  return (
    <div
      className="appShell"
      data-panel={panel}
      data-has-synthesis={activeSynthesis ? "true" : "false"}
    >
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">
            <Database size={22} />
          </div>
          <div>
            <h1>Books Czar</h1>
            <span>Private RAG library</span>
          </div>
        </div>

        <div className={`healthPill ${health?.lmstudio_ok ? "good" : "warn"}`}>
          {health?.lmstudio_ok ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <span>{health?.lmstudio_ok ? "LM Studio online" : "LM Studio offline"}</span>
        </div>

        <nav className="panelTabs" aria-label="Primary panels">
          <button className={panel === "library" ? "active" : ""} onClick={() => openPanel("library")}>
            <Library size={16} />
            Library
          </button>
          <button className={panel === "ask" ? "active" : ""} onClick={() => openPanel("ask")}>
            <MessageSquare size={16} />
            Ask
          </button>

          <button className={panel === "import" ? "active" : ""} onClick={() => openPanel("import")}>
            <Upload size={16} />
            Import
          </button>
          <button className={panel === "synthesis" ? "active" : ""} onClick={() => openPanel("synthesis")}>
            <ClipboardList size={16} />
            Synthesis
          </button>
          <button className={panel === "mastery" ? "active" : ""} onClick={() => openPanel("mastery")}>
            <CheckCircle2 size={16} />
            Mastery
          </button>
          <button className={panel === "settings" ? "active" : ""} onClick={() => openPanel("settings")}>
            <Settings size={16} />
            Settings
          </button>
        </nav>

        <div className="metrics">
          <Metric label="Books" value={books.length} />
          <Metric label="Local" value={storedBooks} />
          <Metric label="Indexed" value={indexedBooks} />
          <Metric label="Chunks" value={health?.chunk_count ?? 0} />
        </div>

        <div className="selectedBox">
          <span>{selectedIds.length || "All"} scoped</span>
          <button
            title="Clear selection"
            onClick={() => setSelectedIds([])}
            disabled={!selectedIds.length}
          >
            Clear
          </button>
        </div>
      </aside>

      <main className="workspace">
        <section className="libraryPane">
          <div className="toolbar">
            <div>
              <h2>{panelTitle(panel)}</h2>
              <span>{selectedBooks.length ? `${selectedBooks.length} selected` : "Full library scope"}</span>
            </div>
            <div className="toolbarActions">
              <button title="Refresh" className="iconButton" onClick={() => void runTask("refreshing", refreshAll)}>
                <RefreshCw size={17} />
              </button>
              <button
                title="Index selected or all local books"
                className="primaryButton"
                onClick={() => void handleIndex(selectedIds.length ? selectedIds : null)}
                disabled={busy === "indexing" || !storedBooks}
              >
                {busy === "indexing" ? <Loader2 className="spin" size={17} /> : <Cpu size={17} />}
                Index
              </button>
            </div>
          </div>

          {notice && <div className="notice success">{notice}</div>}
          {error && <div className="notice error">{error}</div>}
          {busyLabel && busy !== "synthesizing" && <div className="notice neutral">{busyLabel}</div>}

          {panel === "library" && (
            <div className="bookList">
              {books.length === 0 ? (
                <EmptyState />
              ) : (
                books.map((book) => (
                  <BookRow
                    key={book.id}
                    book={book}
                    selected={selectedIds.includes(book.id)}
                    onToggle={() => toggleBook(book.id)}
                    onDelete={() => void handleDelete(book.id)}
                    onAttach={(file) => void handleAttachFile(book.id, file)}
                  />
                ))
              )}
            </div>
          )}

          {panel === "import" && (
            <div className="importGrid">
              <div className="toolPanel wide">
                <div className="toolPanelHeader">
                  <FolderSearch size={18} />
                  <h3>Books Folder</h3>
                </div>
                <div className="compactNote">
                  Put EPUB, PDF, TXT, HTML, or MD files under ./books, then scan.
                </div>
                <button className="secondaryButton" onClick={() => void handleScanBooksFolder()}>
                  <FolderSearch size={17} />
                  Scan ./books
                </button>
              </div>

              <div className="toolPanel">
                <div className="toolPanelHeader">
                  <FileText size={18} />
                  <h3>Files</h3>
                </div>
                <input
                  ref={uploadRef}
                  type="file"
                  multiple
                  accept=".pdf,.epub,.txt,.md,.markdown,.html,.htm"
                  onChange={(event) => void handleBookUpload(event.target.files)}
                />
              </div>

              <div className="toolPanel">
                <div className="toolPanelHeader">
                  <BookOpen size={18} />
                  <h3>Book List</h3>
                </div>
                <input
                  ref={manifestRef}
                  type="file"
                  accept=".csv,.json,.txt"
                  onChange={(event) => void handleManifestUpload(event.target.files)}
                />
                <div className="compactNote">
                  CSV/JSON fields: title, author, url, download_url
                </div>
              </div>

              <div className="toolPanel wide">
                <div className="toolPanelHeader">
                  <Link size={18} />
                  <h3>Direct Downloads</h3>
                </div>
                <textarea
                  value={directUrls}
                  onChange={(event) => setDirectUrls(event.target.value)}
                  placeholder="Title | https://example.com/book.epub"
                />
                <button className="secondaryButton" onClick={() => void handleDirectDownload()}>
                  <ShieldCheck size={17} />
                  Download Authorized URLs
                </button>
              </div>
            </div>
          )}

          {panel === "synthesis" && (
            <div className="synthesisGrid">
              <form className="synthesisForm" onSubmit={(event) => void handleCreateSynthesis(event)}>
                <div className="toolPanelHeader">
                  <ClipboardList size={18} />
                  <h3>Board Brief</h3>
                </div>
                <label>
                  Objective
                  <textarea
                    value={synthesisForm.objective}
                    onChange={(event) =>
                      setSynthesisForm({ ...synthesisForm, objective: event.target.value })
                    }
                    placeholder="What should executives prioritize for AI strategy?"
                  />
                </label>
                <div className="formRow">
                  <label>
                    Audience
                    <select
                      value={synthesisForm.audience}
                      onChange={(event) =>
                        setSynthesisForm({
                          ...synthesisForm,
                          audience: event.target.value as SynthesisAudience
                        })
                      }
                    >
                      {audienceOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Lens
                    <select
                      value={synthesisForm.lens}
                      onChange={(event) =>
                        setSynthesisForm({
                          ...synthesisForm,
                          lens: event.target.value as SynthesisLens
                        })
                      }
                    >
                      {lensOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="scopeSummary">
                  <span>Scope</span>
                  <strong>
                    {synthesisScopeCount
                      ? `${synthesisScopeCount} indexed title${synthesisScopeCount === 1 ? "" : "s"}`
                      : "No indexed titles"}
                  </strong>
                </div>
                <button
                  className="primaryButton"
                  type="submit"
                  disabled={busy === "synthesizing" || !synthesisForm.objective.trim() || !synthesisScopeCount}
                >
                  {busy === "synthesizing" ? <Loader2 className="spin" size={17} /> : <ClipboardList size={17} />}
                  Generate Brief
                </button>
              </form>

              {busy === "synthesizing" && <BuildingBriefStatus />}

              <div className="historyPanel">
                <div className="toolPanelHeader">
                  <History size={18} />
                  <h3>Saved Briefs</h3>
                </div>
                {syntheses.length === 0 ? (
                  <CompactEmpty label="No saved briefs" />
                ) : (
                  <div className="synthesisHistory">
                    {syntheses.map((run) => (
                      <article
                        key={run.id}
                        className={`synthesisRun ${activeSynthesis?.id === run.id ? "active" : ""}`}
                      >
                        <button type="button" onClick={() => void handleOpenSynthesis(run.id)}>
                          <strong>{run.title}</strong>
                          <span>
                            {formatAudience(run.audience)} · {formatLens(run.lens)} · {run.book_ids.length} title
                            {run.book_ids.length === 1 ? "" : "s"}
                          </span>
                          <span>{formatDate(run.created_at)} · {run.status}</span>
                        </button>
                        <button
                          className="iconButton danger"
                          title="Delete synthesis"
                          onClick={() => void handleDeleteSynthesis(run.id)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {panel === "mastery" && (
            <div className="synthesisGrid">
              <form className="synthesisForm" onSubmit={(event) => void handleCreateQuiz(event)}>
                <div className="toolPanelHeader">
                  <CheckCircle2 size={18} />
                  <h3>Mastery Quiz</h3>
                </div>
                <label>
                  Learner name
                  <input
                    value={learnerName}
                    onChange={(event) => setLearnerName(event.target.value)}
                    placeholder="Name for certificate"
                  />
                </label>
                <label>
                  Questions
                  <select
                    value={questionCount}
                    onChange={(event) => setQuestionCount(Number(event.target.value) as 5 | 10 | 15 | 20)}
                  >
                    {questionCountOptions.map((count) => (
                      <option key={count} value={count}>
                        {count} questions
                      </option>
                    ))}
                  </select>
                </label>
                <div className="scopeSummary">
                  <span>Scope</span>
                  <strong>
                    {masteryScopeCount
                      ? `${masteryScopeCount} indexed title${masteryScopeCount === 1 ? "" : "s"}`
                      : "No indexed titles"}
                  </strong>
                </div>
                <button
                  className="primaryButton"
                  type="submit"
                  disabled={busy === "generating quiz" || !masteryScopeCount}
                >
                  {busy === "generating quiz" ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
                  Generate Quiz
                </button>
              </form>

              <div className="historyPanel">
                <div className="toolPanelHeader">
                  <History size={18} />
                  <h3>Saved Quizzes</h3>
                </div>
                {quizzes.length === 0 ? (
                  <CompactEmpty label="No saved quizzes" />
                ) : (
                  <div className="synthesisHistory">
                    {quizzes.map((quiz) => (
                      <article
                        key={quiz.id}
                        className={`synthesisRun ${activeQuiz?.id === quiz.id ? "active" : ""}`}
                      >
                        <button type="button" onClick={() => void handleOpenQuiz(quiz.id)}>
                          <strong>{quiz.title}</strong>
                          <span>
                            {quiz.question_count} questions · {quiz.book_ids.length} title
                            {quiz.book_ids.length === 1 ? "" : "s"}
                          </span>
                          <span>{formatDate(quiz.created_at)} · {quiz.status}</span>
                        </button>
                        <button
                          className="iconButton danger"
                          title="Delete quiz"
                          onClick={() => void handleDeleteQuiz(quiz.id)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {panel === "settings" && (
            <form className="settingsForm" onSubmit={(event) => void handleSaveSettings(event)}>
              <label>
                LM Studio URL
                <input
                  value={settings.lmstudio_base_url}
                  onChange={(event) =>
                    setSettings({ ...settings, lmstudio_base_url: event.target.value })
                  }
                />
              </label>
              <label>
                Chat model
                <select
                  value={settings.chat_model}
                  onChange={(event) => setSettings({ ...settings, chat_model: event.target.value })}
                >
                  {chatModelChoices.map((model) => (
                    <option key={model} value={model}>
                      {model === "local-model" ? "Auto-select chat model" : model}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Embedding model
                <select
                  value={settings.embedding_model}
                  onChange={(event) =>
                    setSettings({ ...settings, embedding_model: event.target.value })
                  }
                >
                  {embeddingModelChoices.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </label>
              <div className="formRow">
                <label>
                  Chunk size
                  <input
                    type="number"
                    min={500}
                    max={5000}
                    value={settings.chunk_size}
                    onChange={(event) =>
                      setSettings({ ...settings, chunk_size: Number(event.target.value) })
                    }
                  />
                </label>
                <label>
                  Overlap
                  <input
                    type="number"
                    min={0}
                    max={1000}
                    value={settings.chunk_overlap}
                    onChange={(event) =>
                      setSettings({ ...settings, chunk_overlap: Number(event.target.value) })
                    }
                  />
                </label>
              </div>
              <button className="primaryButton" type="submit">
                <Settings size={17} />
                Save Settings
              </button>
              <div className="compactNote">
                {modelCatalog.ok
                  ? `${modelCatalog.models.length} LM Studio model${modelCatalog.models.length === 1 ? "" : "s"} available`
                  : modelCatalog.message || health?.lmstudio_message}
              </div>
            </form>
          )}
        </section>

        {panel === "synthesis" ? (
          <section className="chatPane synthesisDetail">
            <div className="chatHeader">
              <div>
                <h2>Synthesis Brief</h2>
                <span>
                  {activeSynthesis
                    ? `${formatAudience(activeSynthesis.audience)} · ${formatLens(activeSynthesis.lens)}`
                    : "No brief selected"}
                </span>
              </div>
              <div className="briefHeaderActions">
                {activeSynthesis?.status === "complete" && !activeSynthesis.error && activeSynthesis.markdown.trim() ? (
                  <button
                    className="secondaryButton briefExportButton"
                    title="Download Microsoft Word document"
                    onClick={() => void handleExportSynthesis(activeSynthesis)}
                    disabled={busy === "exporting Word"}
                  >
                    {busy === "exporting Word" ? <Loader2 className="spin" size={16} /> : <Download size={16} />}
                    Export Word
                  </button>
                ) : null}
                <ClipboardList size={20} />
              </div>
            </div>

            <div className="briefStack">
              {!activeSynthesis ? (
                <div className="chatEmpty">
                  <ClipboardList size={24} />
                  <span>No saved brief selected</span>
                </div>
              ) : (
                <>
                  <BriefAtAGlance run={activeSynthesis} />
                  {activeSynthesis.error ? (
                    <div className="notice error">{activeSynthesis.error}</div>
                  ) : (
                    <BriefArtifact markdown={activeSynthesis.markdown} />
                  )}
                  {activeSynthesis.sources.length ? (
                    <div className="sources briefSources" aria-label="Source evidence">
                      <div className="sourceHeader">
                        <strong>Source Evidence</strong>
                        <span>{activeSynthesis.sources.length} cited passage{activeSynthesis.sources.length === 1 ? "" : "s"}</span>
                      </div>
                      {activeSynthesis.sources.map((source, index) => (
                        <div className="source" key={`${activeSynthesis.id}-${source.book_id}-${source.location}-${index}`}>
                          <strong>[S{index + 1}] {source.title}</strong>
                          <span>{source.location} · {source.score.toFixed(2)}</span>
                          <p>{source.excerpt}</p>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </>
              )}
            </div>
          </section>
        ) : panel === "mastery" ? (
          <section className="chatPane synthesisDetail">
            <div className="chatHeader">
              <div>
                <h2>Knowledge Check</h2>
                <span>
                  {activeQuiz
                    ? `${activeQuiz.question_count} questions · pass ${activeQuiz.passing_score.toFixed(0)}%`
                    : "No quiz selected"}
                </span>
              </div>
              <CheckCircle2 size={20} />
            </div>

            <div className="briefStack">
              {!activeQuiz ? (
                <div className="chatEmpty">
                  <CheckCircle2 size={24} />
                  <span>No saved quiz selected</span>
                </div>
              ) : activeQuiz.error ? (
                <div className="notice error">{activeQuiz.error}</div>
              ) : activeAttempt ? (
                <QuizResultView
                  attempt={activeAttempt}
                  passingScore={activeQuiz.passing_score}
                  onRetake={() => {
                    setActiveAttempt(null);
                    setQuizAnswers({});
                    setActiveQuestionIndex(0);
                  }}
                  onDownload={() => void handleExportCertificate(activeAttempt)}
                  exporting={busy === "exporting certificate"}
                />
              ) : (
                <QuizPlayer
                  quiz={activeQuiz}
                  learnerName={learnerName}
                  answers={quizAnswers}
                  activeIndex={activeQuestionIndex}
                  busy={busy === "scoring quiz"}
                  onAnswer={(questionId, choiceId) =>
                    setQuizAnswers((current) => ({ ...current, [questionId]: choiceId }))
                  }
                  onMove={setActiveQuestionIndex}
                  onSubmit={() => void handleSubmitQuiz()}
                />
              )}
              {quizAttempts.length ? (
                <div className="attemptHistory">
                  <div className="sourceHeader">
                    <strong>Attempt History</strong>
                    <span>{quizAttempts.length} saved</span>
                  </div>
                  {quizAttempts.map((attempt) => (
                    <button
                      type="button"
                      key={attempt.id}
                      className={`attemptRow ${activeAttempt?.id === attempt.id ? "active" : ""}`}
                      onClick={() => setActiveAttempt(attempt)}
                    >
                      <span>{attempt.learner_name}</span>
                      <strong>{attempt.score.toFixed(1)}%</strong>
                      <span>{attempt.passed ? "Passed" : "Needs review"} · {formatDate(attempt.created_at)}</span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </section>
        ) : (
          <section className="chatPane">
            <div className="chatHeader">
              <div>
                <h2>Ask the Czar</h2>
                <span>{selectedIds.length ? `${selectedIds.length} selected title scope` : "All indexed titles"}</span>
              </div>
              <MessageSquare size={20} />
            </div>

            <div className="messageStack">
              {messages.length === 0 ? (
                <div className="chatEmpty">
                  <Search size={24} />
                  <span>Ask from indexed books</span>
                </div>
              ) : (
                messages.map((message) => (
                  <article key={message.id} className={`message ${message.role}`}>
                    <p>{message.content}</p>
                    {message.sources?.length ? (
                      <div className="sources">
                        {message.sources.map((source) => (
                          <div className="source" key={`${message.id}-${source.book_id}-${source.location}`}>
                            <strong>{source.title}</strong>
                            <span>{source.location} · {source.score.toFixed(2)}</span>
                            <p>{source.excerpt}</p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))
              )}
            </div>

            <form className="chatComposer" onSubmit={(event) => void handleChat(event)}>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="What should we learn from this library?"
              />
              <button title="Send" type="submit" disabled={busy === "chat" || !query.trim()}>
                {busy === "chat" ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
              </button>
            </form>
          </section>
        )}
      </main>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function BookRow({
  book,
  selected,
  onToggle,
  onDelete,
  onAttach
}: {
  book: Book;
  selected: boolean;
  onToggle: () => void;
  onDelete: () => void;
  onAttach: (file: File | null) => void;
}) {
  return (
    <article className={`bookRow ${selected ? "selected" : ""}`}>
      <button className="bookSelect" onClick={onToggle} title="Toggle scope">
        {selected ? <CheckCircle2 size={17} /> : <BookOpen size={17} />}
      </button>
      <div className="bookMeta">
        <div className="bookTitle">{book.title}</div>
        <div className="bookSub">
          <span>{book.author || "Unknown author"}</span>
          <span>{book.file_format?.toUpperCase() || book.source}</span>
          <StatusBadge status={book.status} />
        </div>
        {book.note && <div className="bookNote">{book.note}</div>}
      </div>
      <div className="bookStats">
        <span>{book.chunk_count} chunks</span>
        {book.status === "needs_file" && (
          <label className="attachButton" title="Attach local file">
            <Upload size={15} />
            <input
              type="file"
              accept=".pdf,.epub,.txt,.md,.markdown,.html,.htm"
              onChange={(event) => onAttach(event.target.files?.[0] ?? null)}
            />
          </label>
        )}
        <button className="iconButton danger" title="Delete" onClick={onDelete}>
          <Trash2 size={16} />
        </button>
      </div>
    </article>
  );
}

function StatusBadge({ status }: { status: string }) {
  const className = status === "indexed" ? "ok" : status === "error" ? "bad" : status === "needs_file" ? "hold" : "";
  return <span className={`statusBadge ${className}`}>{status.replace("_", " ")}</span>;
}

function EmptyState() {
  return (
    <div className="emptyState">
      <Upload size={28} />
      <span>No books yet</span>
    </div>
  );
}

function CompactEmpty({ label }: { label: string }) {
  return (
    <div className="compactEmpty">
      <span>{label}</span>
    </div>
  );
}

function BuildingBriefStatus() {
  return (
    <div className="buildingBrief">
      <div className="buildingBriefTitle">
        <Loader2 className="spin" size={17} />
        <strong>Building brief</strong>
      </div>
      <div className="buildSteps">
        {["Retrieving evidence", "Comparing themes", "Drafting actions", "Mapping citations"].map((step) => (
          <span key={step}>{step}</span>
        ))}
      </div>
    </div>
  );
}

function QuizPlayer({
  quiz,
  learnerName,
  answers,
  activeIndex,
  busy,
  onAnswer,
  onMove,
  onSubmit
}: {
  quiz: QuizRun;
  learnerName: string;
  answers: Record<string, string>;
  activeIndex: number;
  busy: boolean;
  onAnswer: (questionId: string, choiceId: string) => void;
  onMove: (index: number) => void;
  onSubmit: () => void;
}) {
  const question = quiz.questions[activeIndex];
  const answered = quiz.questions.filter((item) => answers[item.id]).length;
  const complete = answered === quiz.questions.length;
  if (!question) {
    return <CompactEmpty label="This quiz has no questions" />;
  }
  return (
    <article className="quizCard">
      <div className="quizProgress">
        <span>Question {activeIndex + 1} of {quiz.questions.length}</span>
        <strong>{answered}/{quiz.questions.length} answered</strong>
      </div>
      <div className="quizPrompt">
        <h3>{question.prompt}</h3>
        {question.citations.length ? <span>{question.citations.join(", ")}</span> : null}
      </div>
      <div className="choiceGrid">
        {question.choices.map((choice) => (
          <button
            type="button"
            key={choice.id}
            className={answers[question.id] === choice.id ? "selected" : ""}
            onClick={() => onAnswer(question.id, choice.id)}
          >
            <strong>{choice.id}</strong>
            <span>{choice.text}</span>
          </button>
        ))}
      </div>
      <div className="quizActions">
        <button
          type="button"
          className="secondaryButton"
          onClick={() => onMove(Math.max(activeIndex - 1, 0))}
          disabled={activeIndex === 0}
        >
          Previous
        </button>
        {activeIndex < quiz.questions.length - 1 ? (
          <button
            type="button"
            className="secondaryButton"
            onClick={() => onMove(Math.min(activeIndex + 1, quiz.questions.length - 1))}
          >
            Next
          </button>
        ) : (
          <button
            type="button"
            className="primaryButton"
            onClick={onSubmit}
            disabled={busy || !complete || !learnerName.trim()}
          >
            {busy ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
            Submit
          </button>
        )}
      </div>
      {!learnerName.trim() ? <div className="compactNote">Enter a learner name to submit for a certificate.</div> : null}
    </article>
  );
}

function QuizResultView({
  attempt,
  passingScore,
  exporting,
  onRetake,
  onDownload
}: {
  attempt: QuizAttempt;
  passingScore: number;
  exporting: boolean;
  onRetake: () => void;
  onDownload: () => void;
}) {
  const missed = attempt.results.filter((result) => !result.correct);
  return (
    <article className={`quizResult ${attempt.passed ? "passed" : "failed"}`}>
      <div className="quizScore">
        <span>{attempt.passed ? "Mastery achieved" : "Review recommended"}</span>
        <strong>{attempt.score.toFixed(1)}%</strong>
        <p>{attempt.learner_name} · passing score {passingScore.toFixed(0)}%</p>
      </div>
      <div className="quizActions">
        <button type="button" className="secondaryButton" onClick={onRetake}>
          Retake
        </button>
        {attempt.passed ? (
          <button
            type="button"
            className="primaryButton"
            onClick={onDownload}
            disabled={exporting}
          >
            {exporting ? <Loader2 className="spin" size={17} /> : <Download size={17} />}
            Certificate
          </button>
        ) : null}
      </div>
      <div className="reviewList">
        {(missed.length ? missed : attempt.results).map((result) => {
          const selected = result.choices.find((choice) => choice.id === result.selected_choice_id);
          const correct = result.choices.find((choice) => choice.id === result.correct_choice_id);
          return (
            <section key={result.question_id} className={result.correct ? "correct" : "missed"}>
              <h3>{result.prompt}</h3>
              <p>
                Your answer: {selected ? `${selected.id}. ${selected.text}` : "No answer"}
              </p>
              <p>
                Correct answer: {correct?.id}. {correct?.text}
              </p>
              <p>{result.explanation}</p>
            </section>
          );
        })}
      </div>
    </article>
  );
}

function BriefAtAGlance({ run }: { run: SynthesisRun }) {
  return (
    <div className={`briefGlance ${run.status}`}>
      <div>
        <span>Brief at a Glance</span>
        <strong>{run.title}</strong>
      </div>
      <div className="briefGlanceChips">
        <span>{formatAudience(run.audience)}</span>
        <span>{formatLens(run.lens)}</span>
        <span>{run.sources.length} source{run.sources.length === 1 ? "" : "s"}</span>
        <span>{formatDate(run.created_at)}</span>
      </div>
    </div>
  );
}

function BriefArtifact({ markdown }: { markdown: string }) {
  const parsed = parseBriefMarkdown(markdown);
  const featuredTitles = new Set([
    "Recommended 30/60/90 Day Actions",
    "Metrics to Watch",
    "Source Notes"
  ]);
  const narrativeSections = parsed.sections.filter((section) => !featuredTitles.has(section.title));
  return (
    <article className="briefArtifact">
      <div className="briefArtifactHeader">
        <span>Board Brief</span>
        <h2>{parsed.title}</h2>
      </div>

      {parsed.takeaway.length ? (
        <section className="takeawayCallout">
          <span>Executive Takeaway</span>
          {parsed.takeaway.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </section>
      ) : null}

      {(parsed.actions || parsed.metrics) && (
        <div className="briefFocusGrid">
          {parsed.actions && <BriefCompactSection section={parsed.actions} />}
          {parsed.metrics && <BriefCompactSection section={parsed.metrics} />}
        </div>
      )}

      {narrativeSections.map((section) => (
        <BriefSectionView key={section.title} section={section} />
      ))}

      {parsed.sourceNotes && <BriefSectionView section={parsed.sourceNotes} subtle />}
    </article>
  );
}

function BriefCompactSection({ section }: { section: { title: string; lines: string[] } }) {
  const lines = presentableLines(section.lines);
  if (!lines.length) return null;
  return (
    <section className="briefCompactSection">
      <h3>{section.title}</h3>
      <div>
        {lines.map((line) => (
          <p key={line} className={/^(30|60|90)\s+days$/i.test(line) ? "actionMilestone" : ""}>
            {line}
          </p>
        ))}
      </div>
    </section>
  );
}

function BriefSectionView({ section, subtle = false }: { section: { title: string; lines: string[] }; subtle?: boolean }) {
  const lines = presentableLines(section.lines);
  if (!lines.length) return null;
  return (
    <section className={`briefSection ${subtle ? "subtle" : ""}`}>
      <h3>{section.title}</h3>
      {lines.map((line) => (
        <p key={line} className="briefBullet">
          <span aria-hidden="true">•</span>
          {line}
        </p>
      ))}
    </section>
  );
}

function panelTitle(panel: Panel) {
  if (panel === "ask") return "Ask";
  if (panel === "import") return "Import";
  if (panel === "synthesis") return "Synthesis";
  if (panel === "mastery") return "Mastery";
  if (panel === "settings") return "Settings";
  return "Library";
}

function initialPanel(): Panel {
  const hash = window.location.hash.replace("#", "");
  return hash === "ask" || hash === "import" || hash === "synthesis" || hash === "mastery" || hash === "settings" ? hash : "library";
}

function parseDirectUrls(value: string): Array<{ title?: string; url: string }> {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const separator = line.includes("|") ? "|" : ",";
      const parts = line.split(separator).map((part) => part.trim());
      if (parts.length > 1) {
        return { title: parts[0], url: parts.slice(1).join(separator).trim() };
      }
      return { url: line };
    })
    .filter((item) => item.url.startsWith("http://") || item.url.startsWith("https://"));
}

function withCurrentModel(models: string[], current: string): string[] {
  const ordered = current ? [current, ...models] : models;
  return ordered.filter((model, index, all) => model && all.indexOf(model) === index);
}

const audienceOptions: Array<{ value: SynthesisAudience; label: string }> = [
  { value: "board", label: "Board" },
  { value: "c_suite", label: "C-Suite" },
  { value: "cdao_leadership", label: "CDAO Leadership" },
  { value: "technical_leaders", label: "Technical Leaders" }
];

const lensOptions: Array<{ value: SynthesisLens; label: string }> = [
  { value: "all", label: "All" },
  { value: "strategy", label: "Strategy" },
  { value: "risk_governance", label: "Risk/Governance" },
  { value: "operating_model", label: "Operating Model" },
  { value: "investment", label: "Investment" },
  { value: "talent_change", label: "Talent/Change" }
];

const questionCountOptions: Array<5 | 10 | 15 | 20> = [5, 10, 15, 20];

function formatAudience(value: SynthesisAudience) {
  return audienceOptions.find((option) => option.value === value)?.label ?? value;
}

function formatLens(value: SynthesisLens) {
  return lensOptions.find((option) => option.value === value)?.label ?? value;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}
