# Confluence-summarizer Agents Architecture

This document describes the chain of responsibility and personas for the agents involved in refining Confluence documentation.

## Personas & Responsibilities

1. **Ingestor (Service)**
   - Extracts pages from the Confluence space.
   - Handles pagination, rate limits, and cleans up raw HTML/Wiki markup.

2. **Retriever (Service/RAG)**
   - Indexes text chunks into a vector database (ChromaDB).
   - Provides relevant context for a given page to check for inconsistencies and overall coherence.

3. **Analyst Agent**
   - **Role:** Reads the raw text and provided context to identify flaws, outdated information, or formatting issues.
   - **Input:** Page content, RAG context.
   - **Output:** A list of critiques (flaw description, severity, suggestion).

4. **Writer Agent**
   - **Role:** Rewrites the content based on the Analyst's critiques, ensuring standardization, factual consistency, and the style guide.
   - **Input:** Original text, critiques, RAG context.
   - **Output:** The new rewritten document in Markdown format.

5. **Reviewer Agent**
   - **Role:** Reviews the Writer's output against the original text and critiques to ensure it is coherent, correct, and improved.
   - **Input:** Original text, rewritten text, critiques.
   - **Output:** Review decision (Accepted, Completed, etc.) and optional feedback.
