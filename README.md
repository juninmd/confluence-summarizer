# Confluence Refiner

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
- **API**: FastAPI for job management (`/refine/{page_id}`, `/status/{page_id}`).

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
   uv run uvicorn src.confluence_refiner.main:app --reload
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
