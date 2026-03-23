import asyncio
import logging
from typing import Set, Any

from fastapi import FastAPI

from confluence_summarizer.config import settings
from confluence_summarizer.database import init_db
from confluence_summarizer.services import confluence, rag

logger = logging.getLogger(__name__)

REFINEMENT_CONCURRENCY = 5
INGESTION_CONCURRENCY = 10

_background_tasks: Set[asyncio.Task[Any]] = set()


async def _perform_refinement(job_id: str, page_id: str) -> None:
    from confluence_summarizer.database import update_job_status
    from confluence_summarizer.models import RefinementStatus
    from confluence_summarizer.agents.analyst import analyze_page
    from confluence_summarizer.agents.writer import rewrite_page
    from confluence_summarizer.agents.reviewer import review_page

    try:
        await update_job_status(job_id, RefinementStatus.IN_PROGRESS)

        logger.info(f"[{job_id}] Fetching page {page_id}")
        page = await confluence.get_page(page_id)

        logger.info(f"[{job_id}] Ingesting page {page_id} to RAG")
        await rag.ingest_page(page)

        logger.info(f"[{job_id}] Analyzing page {page_id}")
        critiques = await analyze_page(page.content)

        logger.info(f"[{job_id}] Searching context for page {page_id}")
        # Search for context using page title and critiques
        search_query = f"{page.title} " + " ".join([c.issue for c in critiques])
        context_chunks = await rag.search(search_query, page.space_key, n_results=3)

        logger.info(f"[{job_id}] Rewriting page {page_id}")
        final_draft = await rewrite_page(page.content, critiques, context_chunks)

        logger.info(f"[{job_id}] Reviewing page {page_id}")
        status, feedback = await review_page(page.content, final_draft, critiques)

        if status == RefinementStatus.COMPLETED:
            logger.info(f"[{job_id}] Successfully refined page {page_id}")
            await update_job_status(job_id, status)
        else:
            logger.warning(f"[{job_id}] Review failed: {feedback}")
            await update_job_status(job_id, status, error=feedback)

    except Exception as e:
        logger.exception(f"[{job_id}] Refinement process failed: {e}")
        await update_job_status(job_id, RefinementStatus.FAILED, error=str(e))
