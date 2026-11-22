# AGENTS.md

Confluence Summarizer: a Python service that backs up Confluence spaces to Markdown (with PostgreSQL + pgvector indexing), curates duplicated pages with LLM agents, and refines single pages through an Analyst, Writer and Reviewer flow. Overview and API: [`README.md`](README.md).

## Stack

- Python >= 3.11.5, managed by uv (`uv.lock`), hatchling build
- FastAPI, Uvicorn, Pydantic and pydantic-settings, Typer CLI
- PostgreSQL 16 with pgvector (asyncpg). Redis is optional (`REDIS_URL`), used by the RAG service. slowapi rate-limits the API (`src/deps.py`)
- Any OpenAI-compatible LLM and embedding endpoint (`LLM_BASE_URL`, `EMBEDDING_BASE_URL`)

## Commands

- Install: `uv sync`
- API: `uv run uvicorn src.main:app --reload`
- CLI: `uv run python -m src.cli --help`
- Test: `uv run pytest` (pytest-asyncio in auto mode). PostgreSQL integration tests skip when the database is missing
- Typecheck: `uv run pyright` (strict; covers `src` and `tests`)
- Lint: `uv run flake8` (max line 120, `.flake8`)
- Security scan: `uv run bandit -r src` (dev dependency)
- Local services: `docker compose up` (pgvector, vLLM, TEI)

## Structure

- `src/main.py`: FastAPI app. `src/routes*.py`: HTTP routes (backup, curation, core)
- `src/cli.py`: Typer CLI
- `src/backup/`: Confluence to Markdown backup, conversion, layout, verification
- `src/curation/`: clustering, unification, review queue, export
- `src/agents/`: Analyst, Writer, Reviewer and orchestrator for single-page refinement
- `src/services/`: Confluence client, embeddings, RAG. `src/db/`: queries and schema. `src/models/`: domain models
- `src/config.py`: settings (pydantic-settings). `.env.example` lists the variables
- `tests/`: pytest suites and fakes (`tests/fakes.py`)
- `agents.md` (lowercase): architecture of the agent personas. It is a different file from this one
- `GEMINI.md`: agent memory file. `ROADMAP.md`: planned work

## Conventions

- DRY, KISS, SOLID, YAGNI. Implement only what the task needs.
- Max 180 lines of code per file. Split by responsibility when a file grows.
- Docstrings on functions and modules. Comments explain the *why* only.
- Errors are handled predictably, with informative messages. Log for debugging and monitoring, never log secrets or PII.
- Treat data as immutable. Version every persisted change.
- Validate and sanitize external input (Confluence, LLM output, HTTP).
- Tests: cover critical logic and edge cases. Target: 80% coverage. Coverage is not enforced in `pyproject.toml`.
- Code must pass `pyright` (strict) and `flake8` before a PR.

## Gotchas

- Configuration comes from environment variables read by `src/config.py`. Copy `.env.example` to `.env` locally. Never commit `.env` or keys.
- Root CI (`validate.yml`) calls only the reusable validate workflow from `juninmd/base-actions`. Run `pytest`, `pyright` and `flake8` locally before opening a PR.
- The PostgreSQL tests (`tests/test_pg_integration.py`) skip unless the pgvector database is available.
- Backups are written under `BACKUP_DIR` (default `backup`). Pages deleted in Confluence stay on disk and are flagged `deleted`.
- Two agent doc files differ only by case (`AGENTS.md`, `agents.md`). On case-insensitive filesystems they collide. Do not rename either without a plan.

<!-- base-actions-main-policy -->
## GitHub Actions — padrão obrigatório (@main)

- Referencie as actions internas sempre pelo branch, nunca por SHA:
  - `uses: juninmd/base-actions/<action>@main`
  - `uses: juninmd/base-actions/.github/workflows/<arquivo>.yml@main`
- Não fixe `@<sha>` em `juninmd/base-actions`: a atualização é centralizada no
  `main` e passa a valer no próximo run.
- PRs cujos checks não iniciam por billing/spending limit são mesclados pelo bot central
  `juninmd/base-actions/.github/workflows/auto-merge-billing-blocked.yml`.
  Para impedir o merge automático de um PR, aplique a label `do-not-merge`.
