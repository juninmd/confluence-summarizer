import asyncio
import logging
import uuid

from src.confluence_summarizer.agents import analyst, reviewer, writer
from src.confluence_summarizer.database import save_job
from src.confluence_summarizer.deps import (
    background_tasks_set,
    ingestion_semaphore,
    refinement_semaphore,
)
from src.confluence_summarizer.models.domain import (
    ConfluencePage,
    RefinementJob,
    RefinementStatus,
)
from src.confluence_summarizer.services import confluence, rag

logger = logging.getLogger(__name__)


async def _perform_refinement(job: RefinementJob, page: ConfluencePage):
    """Core logic to refine a single Confluence page.

    Args:
        job (RefinementJob): The refinement job to process.
        page (ConfluencePage): The original Confluence page to refine.
    """
    try:
        # Step 1: Query Context
        logger.info(f"Querying context for job {job.id}")
        context = await rag.query_context(page.body, n_results=5)

        # Step 2: Analyst Agent
        logger.info(f"Analyzing content for job {job.id}")
        analysis = await analyst.analyze_content(page.body, context)

        if not analysis.critiques:
            logger.info(f"No critiques found for job {job.id}. Marking as completed.")
            job.status = RefinementStatus.COMPLETED
            job.refined_text = page.body
            await save_job(job)
            return

        # Step 3: Writer Agent
        logger.info(f"Rewriting content for job {job.id}")
        rewritten_text = await writer.rewrite_content(page.body, analysis, context)

        # Step 4: Reviewer Agent
        logger.info(f"Reviewing content for job {job.id}")
        review = await reviewer.review_content(page.body, rewritten_text, analysis)

        if review.status == RefinementStatus.COMPLETED:
            job.status = RefinementStatus.COMPLETED
            job.refined_text = rewritten_text
        else:
            job.status = RefinementStatus.FAILED
            job.error = f"Reviewer rejected changes. Reason: {review.feedback}"

    except Exception as e:
        logger.exception(f"Error processing job {job.id}")
        job.status = RefinementStatus.FAILED
        job.error = str(e)

    await save_job(job)


async def process_refinement_job(job: RefinementJob):
    """Background task to run a single refinement job with semaphore.

    Args:
        job: The refinement job to process.
    """
    async with refinement_semaphore:
        try:
            logger.info(
                f"Starting background processing for job {job.id} (Page: {job.page_id})"
            )
            page = await confluence.get_page(job.page_id)
            job.original_text = page.body
            await save_job(job)

            await _perform_refinement(job, page)

        except Exception as e:
            logger.exception(f"Failed to start refinement for job {job.id}")
            job.status = RefinementStatus.FAILED
            job.error = str(e)
            await save_job(job)


async def _ingest_with_sem(page: ConfluencePage):
    async with ingestion_semaphore:
        await rag.ingest_page(page)


async def _process_with_page(j: RefinementJob, p: ConfluencePage):
    async with refinement_semaphore:
        try:
            logger.info(
                f"Starting background processing for job {j.id} (Page: {j.page_id})"
            )
            await _perform_refinement(j, p)
        except Exception as e:
            logger.exception(f"Failed to start refinement for job {j.id}")
            # Fix the loop variable capture issue
            j.status = RefinementStatus.FAILED
            j.error = str(e)
            await save_job(j)


async def process_space_refinement(space_key: str):
    """Background task to process an entire Confluence space.

    Args:
        space_key: The space key to process.
    """
    try:
        logger.info(f"Starting space processing for space: {space_key}")
        pages = await confluence.get_pages_from_space(space_key)
        logger.info(f"Fetched {len(pages)} pages from space {space_key}")

        ingestion_tasks = [_ingest_with_sem(page) for page in pages]
        await asyncio.gather(*ingestion_tasks)
        logger.info(f"Completed ingestion for space {space_key}")

        for page in pages:
            job = RefinementJob(
                id=str(uuid.uuid4()),
                page_id=page.id,
                status=RefinementStatus.PENDING,
                original_text=page.body,
            )
            await save_job(job)
            task = asyncio.create_task(_process_with_page(job, page))
            background_tasks_set.add(task)
            task.add_done_callback(background_tasks_set.discard)

    except Exception:
        logger.exception(f"Error processing space {space_key}")
