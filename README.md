# ConfluenceRefiner

A robust system to refine Confluence documentation using AI agents. This system connects to Confluence, ingests pages, indexes them for RAG (Retrieval-Augmented Generation), and uses a multi-agent system to analyze, rewrite, and review content.

## Architecture

The system follows a Chain of Responsibility pattern with three main agents:
1.  **Analyst Agent**: Critiques the content for clarity, accuracy, and formatting.
2.  **Writer Agent**: Rewrites the content based on critiques.
3.  **Reviewer Agent**: Validates the rewritten content.

**Tech Stack:**
-   **Language**: Python 3.11+
-   **Framework**: FastAPI
-   **Package Manager**: `uv`
-   **Type Checking**: `pyright` (strict)
-   **Linting**: `flake8`
-   **Vector DB**: ChromaDB (local)
-   **Persistence**: SQLite (for job status)

## Setup

1.  **Install `uv`**:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Install dependencies**:
    ```bash
    uv sync
    ```

3.  **Environment Variables**:
    Create a `.env` file with the following:
    ```env
    CONFLUENCE_URL=https://your-domain.atlassian.net/wiki
    CONFLUENCE_USERNAME=your-email@example.com
    CONFLUENCE_API_TOKEN=your-api-token
    OPENAI_API_KEY=your-openai-api-key
    CHROMA_DB_PATH=./chroma_db
    DB_PATH=jobs.db
    ```

## Usage

Start the server:
```bash
uv run uvicorn confluence_refiner.main:app --reload
```
(Note: ensure you are running from the `src` directory or adjust pythonpath, e.g. `uv run uvicorn confluence_refiner.main:app` if installed in editable mode, or `python -m confluence_refiner.main`)

### Endpoints

-   `POST /refine/{page_id}`: Start refining a page.
-   `GET /status/{page_id}`: Check the status of a refinement job.
-   `POST /publish/{page_id}`: Publish the refined page back to Confluence.
-   `POST /ingest/space/{space_key}`: Ingest an entire space into the vector DB.

## Development

Run tests:
```bash
uv run pytest
```

Run type checking:
```bash
uv run pyright src
```

Run linter:
```bash
uv run flake8 src
```
