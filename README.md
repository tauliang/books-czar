# Books Czar

Books Czar is a private RAG workbench for an executive technical library.
It imports local books, indexes them with an LM Studio embedding model, and
answers questions through an LM Studio chat model with cited local passages.

Supported paths:

- Upload authorized local `.epub`, `.pdf`, `.txt`, `.md`, or `.html` files.
- Put authorized local `.epub`, `.pdf`, `.txt`, `.md`, or `.html` files under
  `./books` and scan the folder from the app.
- Import a book list as CSV/JSON so titles can be tracked locally.
- Download direct `.epub`, `.pdf`, `.txt`, `.md`, or `.html` URLs only when those
  URLs are already authorized for local download.

## Requirements

- Python 3.11+
- Node.js 20+
- LM Studio with the local server enabled
- A loaded chat model and embedding model in LM Studio

Default LM Studio API settings:

- Base URL: `http://127.0.0.1:1234/v1`
- Chat model: `local-model` auto-selects the first non-embedding model LM Studio exposes
- Embeddings: `text-embedding-nomic-embed-text-v1.5`

## Run

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Local Books Folder

By default, Books Czar scans `./books` recursively. You can change that with
`BOOKWISE_BOOKS_DIR`.

```text
books/
  ai-strategy.epub
  data-platforms/
    architecture.pdf
  notes.md
```

In the app, open Import and click `Scan ./books`, then click `Index`.

## Manifest Formats

CSV:

```csv
title,author,url,download_url
Designing Data-Intensive Applications,Martin Kleppmann,https://example.com/catalog/designing-data-intensive-applications,
```

JSON:

```json
{
  "books": [
    {
      "title": "Example Book",
      "author": "Example Author",
      "url": "https://example.com/catalog/example",
      "download_url": "https://example.com/example.epub"
    }
  ]
}
```

## API

- `POST /api/books/upload` uploads local files.
- `POST /api/books/manifest` queues a CSV/JSON title list.
- `POST /api/books/download` downloads authorized direct file URLs.
- `POST /api/index` embeds stored books into SQLite.
- `POST /api/chat` performs retrieval and asks LM Studio for an answer.

## Data

Local files, SQLite metadata, chunks, and embeddings live under `./data` by default.
Set `BOOKWISE_DATA_DIR` to move the library.

## RAG Pattern

This application uses Retrieval-Augmented Generation:

1. Ingest local books from upload, manifest, direct download, or `./books`.
2. Parse text from EPUB/PDF/TXT/HTML/MD files.
3. Chunk the text and create embeddings through LM Studio.
4. Store chunks and embeddings in SQLite.
5. Embed the user question, retrieve the most similar chunks, and send only
   those excerpts as context to the local chat model.
6. Return the model answer with source excerpts and similarity scores.
