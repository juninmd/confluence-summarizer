from dotenv import load_dotenv
load_dotenv()

import logging  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
import asyncio  # noqa: E402
from fastapi import FastAPI, BackgroundTasks, HTTPException  # noqa: E402
from .models import RefinementResult, RefinementStatus, ConfluencePage  # noqa: E402
from .services import confluence, rag  # noqa: E402
from .agents import refine_page  # noqa: E402
from . import database  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing application resources...")
    await database.init_db()
    confluence.init_client()
    yield
    logger.info("Cleaning up application resources...")
    await confluence.close_client()


app = FastAPI(
    title="Confluence Refiner",
    description="A robust system to refine and standardize Confluence documentation using AI Agents.",
    version="0.1.0",
    lifespan=lifespan
)


async def process_refinement(page_id: str) -> None:
    """
    Background task to process the refinement of a single page.
    """
    logger.info(f"Starting refinement for page {page_id}")
    try:
        page = await confluence.get_page(page_id)
        result = await refine_page(page)
        await database.save_job(result)
        logger.info(f"Refinement completed for page {page_id} with status {result.status}")
    except Exception as e:
        logger.error(f"Refinement failed for page {page_id}: {e}", exc_info=True)
        # Update job with error
        result = RefinementResult(
            page_id=page_id,
            original_content="",
            status=RefinementStatus.FAILED,
            reviewer_comments=str(e)
        )
        await database.save_job(result)


async def process_space_ingestion(space_key: str):
    logger.info(f"Starting ingestion for space {space_key}")
    try:
        pages = await confluence.get_pages_from_space(space_key)
        logger.info(f"Found {len(pages)} pages in space {space_key}")
        sem = asyncio.Semaphore(10)

        async def ingest_with_sem(page: ConfluencePage):
            async with sem:
                await rag.ingest_page(page)

        await asyncio.gather(*(ingest_with_sem(page) for page in pages))
        logger.info(f"Ingestion completed for space {space_key}")
    except Exception as e:
        logger.error(f"Error ingesting space {space_key}: {e}", exc_info=True)


@app.post("/refine/{page_id}")
async def start_refinement(page_id: str, background_tasks: BackgroundTasks):
    """
    Starts a refinement job for a specific page.
    """
    logger.info(f"Received refinement request for page {page_id}")
    job = RefinementResult(
        page_id=page_id,
        original_content="",
        status=RefinementStatus.PROCESSING
    )
    await database.save_job(job)
    background_tasks.add_task(process_refinement, page_id)
    return {"message": "Refinement job started", "page_id": page_id}


@app.get("/status/{page_id}", response_model=RefinementResult)
async def get_status(page_id: str):
    """
    Checks the status of a refinement job.
    """
    result = await database.get_job(page_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@app.post("/ingest/space/{space_key}")
async def ingest_space(space_key: str, background_tasks: BackgroundTasks):
    """
    Triggers ingestion of all pages in a space into the vector DB.
    """
    logger.info(f"Received ingestion request for space {space_key}")
    background_tasks.add_task(process_space_ingestion, space_key)
    return {"message": f"Ingestion started for space {space_key}"}


@app.post("/publish/{page_id}")
async def publish_page(page_id: str):
    """
    Publishes the refined content to Confluence.
    """
    logger.info(f"Received publish request for page {page_id}")
    result = await database.get_job(page_id)

    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    if result.status != RefinementStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Job status is {result.status}, cannot publish")

    if not result.rewritten_content:
        raise HTTPException(status_code=400, detail="No rewritten content available")

    try:
        current_page = await confluence.get_page(page_id)

        await confluence.update_page(
            page_id=page_id,
            title=current_page.title,  # Keep original title for now
            body=result.rewritten_content,
            version_number=current_page.version
        )
        logger.info(f"Successfully published page {page_id}")
        return {"message": "Page published successfully", "page_id": page_id}
    except Exception as e:
        logger.error(f"Failed to publish page {page_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to publish: {str(e)}")
