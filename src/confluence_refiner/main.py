from typing import Dict
from fastapi import FastAPI, BackgroundTasks, HTTPException
from .models import RefinementResult, RefinementStatus
from .services import confluence, rag
from .agents import refine_page

app = FastAPI(title="Confluence Refiner")

# In-memory job store (replace with Redis/DB in production)
jobs: Dict[str, RefinementResult] = {}


async def process_refinement(page_id: str):
    try:
        page = await confluence.get_page(page_id)
        result = await refine_page(page)
        jobs[page_id] = result
    except Exception as e:
        # Update job with error
        jobs[page_id] = RefinementResult(
            page_id=page_id,
            original_content="",
            status=RefinementStatus.FAILED,
            reviewer_comments=str(e)
        )


async def process_space_ingestion(space_key: str):
    try:
        pages = await confluence.get_pages_from_space(space_key)
        for page in pages:
            rag.ingest_page(page)
    except Exception as e:
        print(f"Error ingesting space {space_key}: {e}")


@app.post("/refine/{page_id}")
async def start_refinement(page_id: str, background_tasks: BackgroundTasks):
    """
    Starts a refinement job for a specific page.
    """
    jobs[page_id] = RefinementResult(
        page_id=page_id,
        original_content="",
        status=RefinementStatus.PROCESSING
    )
    background_tasks.add_task(process_refinement, page_id)
    return {"message": "Refinement job started", "page_id": page_id}


@app.get("/status/{page_id}", response_model=RefinementResult)
async def get_status(page_id: str):
    """
    Checks the status of a refinement job.
    """
    if page_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[page_id]


@app.post("/ingest/space/{space_key}")
async def ingest_space(space_key: str, background_tasks: BackgroundTasks):
    """
    Triggers ingestion of all pages in a space into the vector DB.
    """
    background_tasks.add_task(process_space_ingestion, space_key)
    return {"message": f"Ingestion started for space {space_key}"}


@app.post("/publish/{page_id}")
async def publish_page(page_id: str):
    """
    Publishes the refined content to Confluence.
    """
    if page_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    result = jobs[page_id]

    if result.status != RefinementStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Job status is {result.status}, cannot publish")

    if not result.rewritten_content:
        raise HTTPException(status_code=400, detail="No rewritten content available")

    # Fetch current page to get version
    # Note: In a real scenario we should have stored the version or handle optimistic locking.
    # For now, we fetch fresh.
    try:
        current_page = await confluence.get_page(page_id)

        await confluence.update_page(
            page_id=page_id,
            title=current_page.title,  # Keep original title for now
            body=result.rewritten_content,
            version_number=current_page.version
        )

        return {"message": "Page published successfully", "page_id": page_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish: {str(e)}")
