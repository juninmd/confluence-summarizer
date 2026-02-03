# ConfluenceRefiner

ConfluenceRefiner is an AI-powered system designed to ingest, analyze, and refine Confluence documentation. It leverages a Chain of Responsibility pattern with specialized agents (Analyst, Writer, Reviewer) and a RAG (Retrieval-Augmented Generation) system to ensure documentation is clear, accurate, and consistent.

## Features

-   **Agentic Workflow**:
    -   **Analyst**: Critiques content for clarity, accuracy, and tone.
    -   **Writer**: Rewrites content based on critiques.
    -   **Reviewer**: Validates the output.
-   **RAG Integration**: Uses ChromaDB to provide context-aware analysis and prevent hallucinations.
-   **Async Architecture**: Built with FastAPI and asyncio for high performance.
-   **Persistence**: SQLite-backed job storage.

## Setup

1.  **Prerequisites**: Python 3.11+, `uv` (Universal Python Packaging).
2.  **Install Dependencies**:
    ```bash
    uv sync --all-extras --dev
    ```
3.  **Environment Variables**:
    Create a `.env` file (or set variables):
    -   `CONFLUENCE_URL`
    -   `CONFLUENCE_USERNAME`
    -   `CONFLUENCE_API_TOKEN`
    -   `CHROMA_DB_PATH` (optional, defaults to `./chroma_db`)

## Usage

Start the server:
```bash
uv run fastapi dev src/confluence_refiner/main.py
```

Endpoints:
-   `POST /refine/{page_id}`: Start refining a page.
-   `GET /status/{page_id}`: Check job status.
-   `POST /publish/{page_id}`: Publish refined content to Confluence.
-   `POST /ingest/space/{space_key}`: Ingest a space into the RAG system.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md).
