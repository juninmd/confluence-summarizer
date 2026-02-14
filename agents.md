# Agent Architecture - ConfluenceSummarizer

This document defines the personas and workflow of the AI agents in the **ConfluenceSummarizer** system.

## Overview
The system uses a Chain of Responsibility pattern where each agent has a specific role in refining documentation.

## Personas

### 1. Analyst Agent
**Responsibility:** Read the raw text extracted from Confluence and identify issues.
**Input:** Page text (raw), Metadata.
**Output:** Structured list of critiques (issues).
**Analysis Criteria:**
- Clarity and conciseness.
- Freshness (dates, software versions mentioned).
- Formatting (headers, code blocks).
- Tone (should be technical and formal).

### 2. Writer Agent
**Responsibility:** Rewrite the content based on Analyst critiques and the Style Guide.
**Input:** Original text, List of critiques, Related Context (RAG).
**Output:** Refined text (Markdown).
**Guidelines:**
- Fix all critiques pointed out.
- Use provided context to ensure factual consistency.
- Maintain the original logical structure unless it is confusing.
- Ensure code examples are formatted correctly.

### 3. Reviewer Agent
**Responsibility:** Validate the refined text before publication.
**Input:** Refined text, Original text.
**Output:** Status (APPROVED / REJECTED -> Mapped to COMPLETED/REJECTED internally) and Final Comments.
**Criteria:**
- Was the original meaning preserved?
- Is the text hallucinated (invented information)?
- Were the Analyst's critiques resolved?

## Execution Flow

1. **Ingestion:** `ConfluenceService` extracts the page.
2. **Retrieval:** `RAGService` fetches relevant context (related pages) to avoid contradictions.
3. **Analysis:** `Analyst Agent` processes content + context.
4. **Writing:** `Writer Agent` generates the new version using critiques and context.
5. **Review:** `Reviewer Agent` approves or requests adjustments (optional loop, currently linear).
6. **Output:** Final result is returned via API.

## Future Roadmap

### 1. Robust Semantic Search
Implement advanced embedding models and hybrid search (keyword + semantic) in `RAGService` to improve context retrieval accuracy.
- **Action:** Integrate BM25 alongside ChromaDB vector search.

### 2. Interactive Review Loop
Allow the `Reviewer Agent` to send feedback back to the `Writer Agent` automatically if the quality threshold isn't met, creating a self-correcting loop (max retries).
- **Action:** Modify `orchestrator.py` to implement a `while` loop with a max retry counter.

### 3. Analytics Dashboard
Create a frontend (React/Vue) to visualize jobs, compare original vs. refined content (diff view), and manually approve changes before publishing.
- **Action:** Initialize a `frontend/` directory and build a basic job status view.
