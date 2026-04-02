# Product Roadmap: Confluence Summarizer

## 1. Vision & Goals

**Vision:** To build an automated, intelligent documentation refinement system that transforms raw Confluence pages into clear, consistent, and high-quality standard documentation, eliminating manual review overhead.

**Goals:**
*   **Quality & Consistency:** Standardize documentation format, tone, and clarity across all Confluence spaces.
*   **Automation:** Reduce manual editorial effort via an autonomous multi-agent pipeline (Analyst, Writer, Reviewer).
*   **Scalability:** Efficiently process large Confluence spaces leveraging asynchronous operations and Retrieval-Augmented Generation (RAG).
*   **Reliability:** Maintain a robust, error-resistant system that degrades gracefully and provides clear observability.

## 2. Current Status

The core foundation is established, bringing significant initial value. The basic agent pipeline and integration components are currently under review in [PR #44: "feat: implement confluence summarizer system with agents and rag"](https://github.com/juninmd/confluence-summarizer/pull/44).

Currently, the system is capable of:
*   Extracting content securely via the Confluence API.
*   Vectorizing and retrieving context using ChromaDB.
*   Refining content through a collaborative multi-agent process.
*   Handling single-page and batch (space-wide) ingestion via FastAPI endpoints.

However, we are currently blocked by CI pipeline instability which needs immediate resolution to ensure reliable delivery.

## 3. Quarterly Roadmap

### Q1 (Near-Term)
*   **High Priority:**
    *   Resolve critical CI pipeline failures blocking merge/deployment (Issues [#55](https://github.com/juninmd/confluence-summarizer/issues/55) & [#58](https://github.com/juninmd/confluence-summarizer/issues/58)).
    *   Merge the initial system implementation ([PR #44](https://github.com/juninmd/confluence-summarizer/pull/44)) to establish our core baseline.
*   **Medium Priority:**
    *   Enhance RAG context retrieval accuracy by tuning chunk size and overlap to improve the Writer agent's factual consistency.
*   **Low Priority:**
    *   Expand test coverage for agent failure recovery (e.g., handling malformed LLM JSON outputs).

### Q2 (Mid-Term)
*   **High Priority:**
    *   Implement reliable Confluence publish capabilities, ensuring complex macros and formatting are preserved when pushing refined content back.
*   **Medium Priority:**
    *   Improve concurrency and rate-limiting controls for processing massive Confluence spaces to prevent 429 errors.
*   **Low Priority:**
    *   Enhance system observability, adding structured logging for long-running batch ingestion jobs.

### Q3 (Long-Term)
*   **High Priority:**
    *   Develop a pluggable LLM backend architecture to support alternative providers (e.g., Anthropic Claude, open-source models).
*   **Medium Priority:**
    *   Launch an interactive Web UI for job monitoring, allowing non-technical stakeholders to review and approve agent rewrites before publication.
*   **Low Priority:**
    *   Optimize the vector database performance for scaling to thousands of documents.

### Q4 (Future)
*   **High Priority:**
    *   Introduce customizable style guides, allowing teams to define specific rulesets per Confluence space.
*   **Medium Priority:**
    *   Deepen Atlassian integration, such as automatically creating Jira tickets for documentation that requires human intervention or cannot be resolved by agents.
*   **Low Priority:**
    *   Implement Confluence Webhook integration for real-time RAG updates, keeping the vector index perfectly in sync with user edits.

## 4. Feature Details

### Feature: CI Pipeline Stabilization & Core Merge
*   **User Value Proposition:** Ensures that all code changes are reliably tested and validated, allowing for a stable and predictable release cadence.
*   **Technical Approach:** Investigate failing GitHub Actions workflows (Issues #55, #58), fix underlying environment or test issues, and successfully merge PR #44.
*   **Success Criteria:** CI pipeline passes 100% consistently on the default branch (e.g., main) and all open PRs.
*   **Estimated Effort:** Small

### Feature: Reliable Confluence Publishing Mechanism
*   **User Value Proposition:** Closes the loop by automatically pushing polished content back to Confluence, realizing the time-saving benefits of the automated pipeline.
*   **Technical Approach:** Enhance the existing Confluence API integration in src/confluence_summarizer/services/confluence.py to support reliable updates. Implement validation to ensure complex Confluence storage format (macros, tables) is not corrupted during the update.
*   **Success Criteria:** System successfully updates 95%+ of Confluence pages without breaking their native formatting.
*   **Estimated Effort:** Medium

### Feature: Alternative LLM Backend Support
*   **User Value Proposition:** Mitigates vendor lock-in, reduces costs by routing simpler tasks to cheaper models, and provides resilience against provider outages.
*   **Technical Approach:** Abstract the OpenAI client in `src/confluence_summarizer/agents/common.py` into a generic interface and build adapters for Anthropic/local models.
*   **Success Criteria:** The system can toggle between at least two different LLM providers via environment variables without a drop in refinement quality.
*   **Estimated Effort:** Medium

### Feature: Interactive Job Monitoring Web UI
*   **User Value Proposition:** Empowers product and documentation managers to oversee the refinement process, track progress, and visually approve (diff-view) changes before publication.
*   **Technical Approach:** Develop a lightweight React/Vue frontend interfacing with FastAPI's /status/{job_id} and new endpoints for tracking space-wide refinement progress.
*   **Success Criteria:** Users can trigger jobs, view progress bars, and approve/reject specific page updates via the UI.
*   **Estimated Effort:** Large

## 5. Dependencies & Risks

*   **CI Instability (Current Blocker):** Failing CI (Issues #55, #58) is currently blocking our ability to safely merge and deploy.
*   **API Rate Limits:** High dependency on Confluence and LLM API rate limits. Batch jobs could trigger 429s if concurrency (`asyncio.Semaphore`) is not carefully managed.
*   **Content Formatting Integrity:** Confluence uses a complex underlying XML structure (storage format). There is a risk that the LLM may strip or corrupt macros during the rewrite phase.
*   **Database Locking:** The SQLite database is currently sufficient, but at high concurrency, WAL mode might still encounter lock contentions. We must monitor this as we scale space processing.
