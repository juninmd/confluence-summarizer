import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Set, Any, AsyncGenerator, Dict, Coroutine

from dotenv import load_dotenv

load_dotenv()  # flake8: noqa: E402

from fastapi import FastAPI, HTTPException, BackgroundTasks, status

from confluence_summarizer.config import settings
from confluence_summarizer.database import init_db, create_job, get_job, update_job_status
from confluence_summarizer.models import JobStatus, RefinementStatus
from confluence_summarizer.services import confluence, rag

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REFINEMENT_CONCURRENCY = 5
INGESTION_CONCURRENCY = 10

_background_tasks: Set[asyncio.Task[Any]] = set()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    await confluence.init_client()
    yield
    await confluence.close_client()
    for task in _background_tasks:
        task.cancel()


app = FastAPI(title="Confluence Summarizer", lifespan=lifespan)


async def perform_refinement(job_id: str, page_id: str) -> None:
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


async def perform_space_refinement(job_id: str, space_key: str) -> None:
    try:
        await update_job_status(job_id, RefinementStatus.IN_PROGRESS)

        semaphore = asyncio.Semaphore(REFINEMENT_CONCURRENCY)
        tasks = []

        async for page in confluence.get_pages_in_space(space_key):

            async def process_page(page_id: str) -> None:
                async with semaphore:
                    try:
                        # Dummy job sub-process
                        await perform_refinement(job_id, page_id)
                    except Exception as e:
                        logger.error(f"[{job_id}] Failed processing page {page_id}: {e}")

            task = asyncio.create_task(process_page(page.page_id))
            tasks.append(task)

        await asyncio.gather(*tasks)
        await update_job_status(job_id, RefinementStatus.COMPLETED)

    except Exception as e:
        logger.exception(f"[{job_id}] Space refinement failed: {e}")
        await update_job_status(job_id, RefinementStatus.FAILED, error=str(e))


@app.post("/refine/{page_id}", response_model=JobStatus)
async def refine_page(page_id: str, background_tasks: BackgroundTasks) -> JobStatus:
    job = await create_job(page_id=page_id)

    task = asyncio.create_task(perform_refinement(job.job_id, page_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return job


@app.post("/refine/space/{space_key}", response_model=JobStatus)
async def refine_space(space_key: str, background_tasks: BackgroundTasks) -> JobStatus:
    job = await create_job(space_key=space_key)

    task = asyncio.create_task(perform_space_refinement(job.job_id, space_key))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return job


@app.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str) -> JobStatus:
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@app.post("/publish/{job_id}")
async def publish_job(job_id: str) -> Dict[str, str]:
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.status != RefinementStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job is not completed")

    # Dummy publish action
    logger.info(f"[{job_id}] Publishing changes to Confluence for page_id={job.page_id} space_key={job.space_key}")
    return {"message": "Job published successfully"}
