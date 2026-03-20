# Product Roadmap: Confluence Summarizer

## 1. Vision & Goals

**Vision:** To provide a robust, automated system that refines and standardizes Confluence documentation using an advanced AI agent pipeline.

**Goals:**
*   Reduce manual effort required to maintain and update internal documentation.
*   Ensure high documentation quality, clarity, and consistency across spaces.
*   Provide a reliable multi-agent workflow (Analyst, Writer, Reviewer) to autonomously critique, rewrite, and validate content against standard style guides.
*   Maintain seamless integration with Atlassian Confluence via APIs while leveraging scalable RAG (ChromaDB) for context-aware processing.

## 2. Current Status

The project has achieved its initial milestones and a robust core system is currently under review in [PR #44: "feat: implement confluence summarizer system with agents and rag"](https://github.com/juninmd/confluence-summarizer/pull/44).

Current capabilities include:
*   **Ingestion:** Asynchronous Confluence API client with pagination and rate limiting.
*   **Context Retrieval (RAG):** ChromaDB integration for vectorizing and retrieving relevant documentation context.
*   **Multi-Agent Refinement:**
    *   **Analyst:** Identifies clarity, tone, and formatting issues.
    *   **Writer:** Rewrites content based on critiques.
    *   **Reviewer:** Validates the output against original text and critiques.
*   **Job Management:** FastAPI endpoints for triggering single-page and space-wide refinements.

## 3. Quarterly Roadmap

### Q1 (Near-Term)
*   **High Priority:** Merge initial full system implementation ([PR #44](https://github.com/juninmd/confluence-summarizer/pull/44)) and stabilize the multi-agent pipeline.
*   **Medium Priority:** Enhance RAG retrieval accuracy with tuning of chunk sizes and overlap parameters.
*   **Low Priority:** Expand unit test coverage for edge cases in the agent LLM failure recovery.

### Q2 (Mid-Term)
*   **High Priority:** Introduce advanced batch refinement features and improved concurrency controls for massive Confluence spaces.
*   **Medium Priority:** Implement a reliable mechanism to seamlessly publish refined content back to Confluence without breaking complex formatting/macros.
*   **Low Priority:** Enhanced system observability and detailed error logging for long-running ingestion jobs.

### Q3 (Long-Term)
*   **High Priority:** Explore and integrate alternative LLM backends (e.g., Anthropic Claude, open-source models via Ollama) to reduce dependency on a single provider.
*   **Medium Priority:** Develop a lightweight Web UI to monitor refinement jobs and review agent decisions interactively.
*   **Low Priority:** Performance optimization of the vector database for environments with massive documentation repositories.

### Q4 (Future)
*   **High Priority:** Implement advanced customization features, allowing users to define specific style guides and rule sets per Confluence space.
*   **Medium Priority:** Deeper Atlassian ecosystem integration, such as automatically creating Jira tickets for documentation that requires human intervention.
*   **Low Priority:** Implement continuous RAG updates via Confluence Webhooks to keep the vector database instantly in sync with user edits.

## 4. Feature Details

### Feature: Alternative LLM Backend Support
*   **User Value Proposition:** Reduces vendor lock-in, allows cost optimization by routing simpler tasks to cheaper models, and provides fallback mechanisms during provider outages.
*   **Technical Approach:** Abstract the current OpenAI client implementation in `src/confluence_summarizer/agents/common.py` into a provider-agnostic interface. Implement adapters for other providers (e.g., Anthropic, Gemini, local models).
*   **Success Criteria:** System can switch between at least two different LLM providers via environment variables without degrading the quality of the multi-agent refinement output.
*   **Estimated Effort:** Medium

### Feature: Interactive Web UI for Job Monitoring
*   **User Value Proposition:** Provides non-technical stakeholders and documentation managers a user-friendly dashboard to track the progress of batch refinements and approve/reject agent rewrites before they are published to Confluence.
*   **Technical Approach:** Build a lightweight frontend (e.g., React or Vue) that consumes the existing FastAPI endpoints (`/status/{job_id}`). Include a diff-viewer component to compare original vs. rewritten text.
*   **Success Criteria:** Users can trigger space refinements, view real-time job progress, and inspect the Writer/Reviewer outputs through a graphical interface.
*   **Estimated Effort:** Large

## 5. Dependencies & Risks

*   **API Rate Limits:** The system heavily depends on Confluence and OpenAI APIs. Strict rate limiting and concurrency bounding (`asyncio.Semaphore`) must be constantly monitored to prevent 429 errors.
*   **Database Locking:** Job persistence currently uses SQLite. While configured in WAL mode (`PRAGMA journal_mode=WAL`), high concurrency during space-wide refinements could still lead to database locking issues if not managed carefully.
*   **External Service Dependency:** The core capability relies entirely on the availability and performance of external LLMs (currently OpenAI). Outages or degradation in their service directly impact this system's ability to process jobs.
