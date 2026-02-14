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

- `POST /ingest/{page_id}`: Ingest one specific page into ChromaDB (**RAG por página**).
- `POST /ingest/space/{space_key}`: Ingest all pages from a space.

> ✅ **Verificação solicitada:** existe endpoint de geração/atualização da base RAG por página via API: `POST /ingest/{page_id}`.

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

## Testing

Run the test suite:
```bash
uv run pytest
```

Run type checking:
```bash
uv run pyright src
```

## Agents

See `agents.md` for detailed agent personas and workflows.
