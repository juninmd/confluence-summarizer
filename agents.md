# Architecture & Personas: Confluence Summarizer

This project implements a 'Chain of Responsibility' architecture using AI agents. It follows the principles of RAG (Retrieval-Augmented Generation) and Agentic Collaboration.

## Flow of the Process:
1. **Ingestion & Indexing:** Confluence pages are fetched asynchronously and their content is split (chunked) and stored in ChromaDB to allow context-based Retrieval (RAG).
2. **Analysis:** The `Analyst Agent` reads the raw content and identifies issues, structural problems, missing context, and writes out formal critiques.
3. **Drafting/Writing:** The `Writer Agent` takes the page content, the Analyst's critiques, and retrieved context chunks (RAG) to rewrite the page, enforcing technical standardization and consistency.
4. **Reviewing:** The `Reviewer Agent` checks the revised page against the critiques. If it passes validation, it sets the status to 'completed' / 'accepted' for the page to be ready for publishing.

## Personas & Responsibilities:

- **Analyst Agent**:
  - Task: Find flaws, contradictions, and formatting errors.
  - Returns a set of critiques (with a severity field like "high", "medium", "low").

- **Writer Agent**:
  - Task: Refine the original text, guided by the analyst critiques and external context from the entire space.
  - Returns the final drafted markdown/HTML.

- **Reviewer Agent**:
  - Task: Compare the final draft against the original text and the critiques to ensure completeness.
  - Returns a final status ("approved", "completed", "accepted", "rejected", etc.) and feedback.

**Note on execution limits**: Use proper concurrency controls and retry backoffs (tenacity) to avoid Rate Limits.
