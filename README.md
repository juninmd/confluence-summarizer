# Confluence Summarizer

A robust system to refine and standardize Confluence documentation using AI Agents.

## Overview

This system connects to Confluence, ingests pages into a vector database (ChromaDB), and uses a multi-agent AI system (Analyst, Writer, Reviewer) to critique and rewrite documentation.

## Architecture

- **Ingestion**: Async Confluence API client with pagination and rate limiting.
- **RAG**: ChromaDB for context retrieval.
- **Agents**:
  - **Analyst**: Identifies issues in clarity, tone, and formatting.
  - **Writer**: Rewrites content based on critiques and style guide.
  - **Reviewer**: Validates the output.
- **API**: FastAPI for job management and ingestion.

## API Endpoints

### Refinement

- `POST /refine/{page_id}`: Start refinement for one page.
- `POST /refine/space/{space_key}`: Start refinement for all pages in one space.
- `GET /status/{page_id}`: Get current refinement status/result.
- `POST /publish/{page_id}`: Publish completed refined content back to Confluence.

### RAG Ingestion

- `POST /ingest/{page_id}`: Ingest one specific page into ChromaDB (page-level RAG).
- `POST /ingest/space/{space_key}`: Ingest all pages from a space.

## Performance Notes

- The Confluence pagination now supports fetching all pages by default (`limit=None`) while keeping bounded API page size (`page_size <= 50`).
- Space ingestion/refinement use bounded concurrency (`asyncio.Semaphore`) to prevent API overload and improve throughput.
- Reused shared `httpx.AsyncClient` connection pool (initialized in app lifespan) for lower request overhead.

## Setup

1. **Install Dependencies**:
   ```bash
   uv sync
   ```

2. **Environment Variables**:
   Create a `.env` file:
   ```env
   CONFLUENCE_URL=https://your-domain.atlassian.net/wiki
   CONFLUENCE_USERNAME=your-email@example.com
   CONFLUENCE_API_TOKEN=your-api-token
   OPENAI_API_KEY=sk-...
   CHROMA_DB_PATH=./chroma_db
   DB_PATH=jobs.db
   ```

3. **Run the API**:
   ```bash
   uv run uvicorn src.confluence_summarizer.main:app --reload
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

- **OPENAI_API_KEY**: Required for Agent functionality. If missing, the agents will return empty responses or skip processing.
- **CONFLUENCE_CREDENTIALS**: Check that `CONFLUENCE_USERNAME` matches your Atlassian email and `CONFLUENCE_API_TOKEN` is a valid API token (not your password).

### Database Locks

The system uses SQLite in WAL mode. If you encounter "database is locked" errors, ensure no other process (like a DB browser) is holding a write lock on `jobs.db`.

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
