# Jules Memory & Protocol

This file serves as the "Living Memory" for the Jules agent working on the ConfluenceSummarizer repository.

## Repository Context
- **Project:** ConfluenceSummarizer
- **Purpose:** Ingest, analyze, and refine Confluence documentation using AI agents.
- **Tech Stack:** Python 3.11/3.12, FastAPI, ChromaDB (RAG), Pydantic, httpx.
- **Dependency Manager:** uv
- **Testing/Linting:** pytest, pyright (strict), flake8.

## Active Protocols
- **Antigravity Audit:** Periodic comprehensive reviews of the codebase.
- **Mission Mode:** Specialized personas (Bolt, Palette, Sentinel, Spark) for targeted improvements.
- **100-line Rule:** Keep logic changes concise.
- **100% Coverage:** Mandatory for new/modified code.

## Learnings
- **Persistence:** Moved from in-memory dict to SQLite for job storage to prevent data loss.
- **Async Safety:** RAG operations (ChromaDB) are synchronous and must be wrapped in `asyncio.to_thread` to avoid blocking the FastAPI event loop.
- **Code Hygiene:** Consolidated duplicate database modules (`db.py` and `database.py`) into `database.py` to avoid confusion and bugs.
- **Performance:** Ingestion of large spaces should be parallelized (with semaphores) to reduce total time.

## Roadmap
See `agents.md` for the functional roadmap. This file tracks meta-learnings and architectural decisions.
