# Confluence Summarizer

A robust system to refine and standardize Confluence documentation using AI Agents.

## Overview

Three stages, each usable on its own:

1. **Backup** – mirrors every page, blog post, attachment and image of a space to disk as
   Markdown (plus the untouched raw storage format), and indexes it in PostgreSQL/pgvector.
2. **Curation** – groups duplicated/overlapping pages by embedding similarity, detects
   contradictions and outdated content, and writes one unified, standardized document per
   group (with provenance and a human-review queue for unresolved conflicts).
3. **Refinement** – the original single-page Analyst → Writer → Reviewer agent flow.

## Architecture

- **Storage**: PostgreSQL + **pgvector** (HNSW, cosine) for pages, versions, attachments,
  chunks/embeddings, curated documents and provenance. Files (Markdown, raw, binaries) live
  under `BACKUP_DIR`.
- **Models**: any **OpenAI-compatible** endpoint (vLLM, Ollama, TEI, OpenAI) via
  `LLM_BASE_URL` / `EMBEDDING_BASE_URL`. Suggested open models: Qwen3-32B (chat) and
  BAAI/bge-m3 (embeddings, 1024-d).
- **API**: FastAPI. **CLI**: `python -m src.cli`.

### Backup layout

```
backup/<SPACE>/
  _manifest.json                 # inventory, versions, hashes, errors, deleted pages
  _raw/<page_id>/                # body.storage.html, page.json, comments.json
  assets/<sha256>.<ext>          # every attachment + external image, deduplicated
  <parent-slug-id>/<slug-id>/index.md   # mirrors the page tree; YAML front matter
  blog/<slug-id>/index.md
  curated/<title>-<id>.md        # output of the curation stage
```

- Conversion handles Confluence macros (code, info/note/warning/tip, expand, status, jira,
  include, draw.io previews, ADF panels, task lists), tables (GFM, HTML when merged cells)
  and links between pages. Unknown macros are kept as HTML comments, never dropped.
- Images are resolved per page (including images attached to *other* pages and external
  URLs), stored content-addressed and linked with relative paths. Any image that cannot be
  backed up is reported in the manifest and fails `verify`.
- Incremental: unchanged versions are not re-downloaded or re-embedded; pages deleted in
  Confluence stay on disk and are flagged `deleted`.

## API Endpoints

### Backup and curation (new)

- `POST /backup/space/{space_key}?index=true`: back up a space (background job).
- `GET /backup/space/{space_key}`: last manifest summary.
- `GET /backup/space/{space_key}/verify`: check files, links, images and checksums.
- `POST /curate/space/{space_key}?threshold=0.85`: cluster + unify + review (background job).
- `GET /curate/space/{space_key}?doc_status=needs_review`: list curated documents.
- `GET /curate/doc/{id}`: one document with conflicts and source pages.
- `POST /curate/doc/{id}/approve`: human sign-off (locks it against regeneration).

### CLI

```bash
uv run python -m src.cli backup DOC      # exit code 1 if any page failed
uv run python -m src.cli verify DOC
uv run python -m src.cli curate DOC --threshold 0.85
```

### Refinement

- `POST /refine/{page_id}`: Start refinement for one page.
- `POST /refine/space/{space_key}`: Start refinement for all pages in one space.
- `GET /status/{job_id}`: Get current refinement status/result.
- `POST /publish/{job_id}`: Publish completed refined content back to Confluence.

## Setup

1. **Install Dependencies**:
   ```bash
   uv sync
   ```

2. **Start PostgreSQL with pgvector** (and, optionally, local models on a GPU):
   ```bash
   docker compose up -d db
   docker compose --profile models up -d   # vLLM (Qwen3) + TEI (bge-m3)
   ```

3. **Environment Variables**: copy `.env.example` to `secrets/.env` and fill it in. The
   essentials are `CONFLUENCE_*`, `APP_API_KEY`, `DATABASE_URL`, `LLM_BASE_URL`/`LLM_MODEL`
   and `EMBEDDING_BASE_URL`/`EMBEDDING_MODEL`/`EMBEDDING_DIM`. The schema (including
   `CREATE EXTENSION vector`) is created on startup; `EMBEDDING_DIM` must match the model.

4. **Run the API**:
   ```bash
   uv run uvicorn src.main:app --reload
   ```

## Development & Verification

Run the test suite:
```bash
uv run pytest
```

Run type checking:
```bash
uv run pyright src
```

Run linting:
```bash
uv run flake8 src
```

## Agents

See `agents.md` for detailed agent personas and workflows.

## Troubleshooting

### Missing Environment Variables

If you see errors related to `OPENAI_API_KEY` or `CONFLUENCE_URL`, ensure your `.env` file is correctly formatted and located in the root directory.

- **OPENAI_API_KEY / LLM_BASE_URL**: One of them is required for Agent functionality (a self-hosted OpenAI-compatible server needs only `LLM_BASE_URL`). If both are missing, the agents return a mock response.
- **CONFLUENCE_CREDENTIALS**: Check that `CONFLUENCE_USERNAME` matches your Atlassian email and `CONFLUENCE_API_TOKEN` is a valid API token (not your password).

### Database Locks

Refinement job status still lives in SQLite (WAL mode). If you encounter "database is locked" errors, ensure no other process (like a DB browser) is holding a write lock on `jobs.db`.

## Testing

The project maintains high test coverage for core logic.

To run the full test suite with coverage report:

```bash
uv run pytest --cov=src --cov-report=term-missing
```

To run a specific test file:

```bash
uv run pytest tests/test_agents.py
```
