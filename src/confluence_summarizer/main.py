import asyncio
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
import dotenv
from confluence_summarizer.models import RefinementJob, RefinementStatus
from confluence_summarizer.database import init_db, save_job, get_job
from confluence_summarizer.services.confluence import init_client, close_client, get_page_content, get_space_pages
from confluence_summarizer.services.rag import ingest_page, query_context
from confluence_summarizer.agents.analyst import analyze
from confluence_summarizer.agents.writer import rewrite
from confluence_summarizer.agents.reviewer import review

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REFINEMENT_CONCURRENCY = 5
INGESTION_CONCURRENCY = 10

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_client()
    yield
    await close_client()

app = FastAPI(title="Confluence Summarizer", lifespan=lifespan)

class RefinePageRequest(BaseModel):
    space_key: str

class RefineSpaceRequest(BaseModel):
    pass  # Add configuration if needed

async def _perform_refinement(job: RefinementJob) -> None:
    """Core logic to refine a single Confluence page."""
    try:
        # 1. Fetch
        logger.info(f"Refining page {job.page_id}")
        content = await get_page_content(job.page_id)
        job.original_content = content
        job.status = RefinementStatus.PROCESSING
        await save_job(job)

        # 2. Analyze
        logger.info(f"Analyzing page {job.page_id}")
        analysis = await analyze(content)
        if not analysis:
            raise ValueError("Analysis failed.")
        job.analysis = analysis
        await save_job(job)

        # 3. Retrieve Context
        logger.info(f"Querying context for page {job.page_id}")
        context_queries = [critique.finding for critique in analysis.critiques]
        context: List[str] = []
        for q in context_queries:
            results = await query_context(q)
            context.extend(results)

        # 4. Rewrite
        logger.info(f"Rewriting page {job.page_id}")
        rewritten = await rewrite(content, analysis, list(set(context)))
        if not rewritten:
            raise ValueError("Rewrite failed.")
        job.refined_content = rewritten
        await save_job(job)

        # 5. Review
        logger.info(f"Reviewing page {job.page_id}")
        review_res = await review(content, rewritten)
        if not review_res:
            raise ValueError("Review failed.")
        job.review = review_res
        job.status = review_res.status
        await save_job(job)

    except Exception as e:
        logger.error(f"Error refining page {job.page_id}: {e}", exc_info=True)
        job.status = RefinementStatus.FAILED
        job.error_message = str(e)
        await save_job(job)

async def _process_space(space_key: str) -> None:
    """Processes an entire space."""
    try:
        logger.info(f"Fetching pages for space {space_key}")
        pages = await get_space_pages(space_key)

        # Ingest in parallel with concurrency limit
        sem = asyncio.Semaphore(INGESTION_CONCURRENCY)

        async def ingest_task(page: Dict[str, Any]):
            async with sem:
                page_id = page["id"]
                try:
                    content = await get_page_content(page_id)
                    await ingest_page(page_id, space_key, content)
                except Exception as e:
                    logger.warning(f"Failed to ingest page {page_id}: {e}")

        logger.info(f"Ingesting {len(pages)} pages for space {space_key}")
        await asyncio.gather(*(ingest_task(page) for page in pages))

        # Refine in parallel with concurrency limit
        sem_refine = asyncio.Semaphore(REFINEMENT_CONCURRENCY)

        async def refine_task(page: Dict[str, Any]):
            async with sem_refine:
                job = RefinementJob(page_id=page["id"], space_key=space_key)
                await save_job(job)
                await _perform_refinement(job)

        logger.info(f"Refining {len(pages)} pages for space {space_key}")
        await asyncio.gather(*(refine_task(page) for page in pages))
        logger.info(f"Finished processing space {space_key}")

    except Exception as e:
        logger.error(f"Error processing space {space_key}: {e}", exc_info=True)


@app.post("/refine/{page_id}")
async def refine_page(page_id: str, request: RefinePageRequest, background_tasks: BackgroundTasks):
    job = await get_job(page_id)
    if not job:
        job = RefinementJob(page_id=page_id, space_key=request.space_key)
        await save_job(job)

    background_tasks.add_task(_perform_refinement, job)
    return {"message": "Refinement started.", "page_id": page_id}


@app.post("/refine/space/{space_key}")
async def refine_space(space_key: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(_process_space, space_key)
    return {"message": f"Space refinement started for {space_key}."}


@app.get("/status/{page_id}")
async def get_page_status(page_id: str):
    job = await get_job(page_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
