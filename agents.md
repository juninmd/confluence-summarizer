# Agents Architecture

This document defines the roles and responsibilities of the AI agents in the Confluence-summarizer system. The system uses a "Chain of Responsibility" architecture to ingest, index (RAG with ChromaDB), and refine Confluence pages.

## Personas

1.  **Analyst Agent**
    *   **Role**: Analyzes raw text extracted from Confluence.
    *   **Responsibilities**: Identifies flaws, outdated information, missing formatting, or inconsistencies in the documentation. Outputs a structured critique with specific findings and severity levels.
    *   **Input**: Raw Confluence page text.
    *   **Output**: Structured critique.

2.  **Writer Agent**
    *   **Role**: Rewrites and refines the content.
    *   **Responsibilities**: Uses the Analyst's critique, the original text, and retrieved context (RAG) to rewrite the documentation, ensuring factual consistency, standardization, and clarity.
    *   **Input**: Raw Confluence page text, Analyst critique, retrieved context.
    *   **Output**: Rewritten documentation.

3.  **Reviewer Agent**
    *   **Role**: Quality assurance.
    *   **Responsibilities**: Compares the rewritten documentation against the original to ensure all critiques were addressed and no unintended changes or hallucinations were introduced.
    *   **Input**: Original text, rewritten text.
    *   **Output**: Final review status (APPROVED, REJECTED, NEEDS_REVISION) and comments.
