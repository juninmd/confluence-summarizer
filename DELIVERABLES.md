# Deliverables

## 1. Directory Structure

```
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── src/
│   └── confluence_summarizer/
│       ├── __init__.py
│       ├── main.py
│       ├── models.py
│       ├── database.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── analyst.py
│       │   ├── writer.py
│       │   ├── reviewer.py
│       │   ├── common.py
│       │   └── orchestrator.py
│       └── services/
│           ├── __init__.py
│           ├── confluence.py
│           └── rag.py
├── tests/
│   ├── test_agents.py
│   ├── test_confluence.py
│   ├── test_db.py
│   ├── test_main.py
│   ├── test_main_tasks.py
│   ├── test_orchestrator.py
│   ├── test_rag.py
│   └── test_reviewer_robustness.py
├── agents.md
├── pyproject.toml
└── README.md
```

## 2. pyproject.toml

This file is configured for `uv` with strict type checking and linting dependencies.

## 3. agents.md

The `agents.md` file in the root directory defines the personas (Analyst, Writer, Reviewer) and the execution flow.

## 4. CI/CD Workflow

The `.github/workflows/ci.yml` file is configured to run:
- `uv sync`
- `flake8`
- `pyright`
- `pytest` with coverage

## 5. Source Code

The source code is located in `src/confluence_summarizer/` and follows the architecture:
- **Services**: `confluence.py` (Ingestion), `rag.py` (Retrieval/ChromaDB).
- **Agents**: `analyst.py`, `writer.py`, `reviewer.py`.
- **API**: `main.py` (FastAPI).

## 6. Unit Tests

The `tests/` directory contains full coverage.
An example test case was added to `tests/test_agents.py` (`test_analyst_missing_severity`) to verify robustness against malformed LLM responses.
