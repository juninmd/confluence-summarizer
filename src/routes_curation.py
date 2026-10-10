"""HTTP endpoints for the curation pipeline."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from src.curation.export import export_doc
from src.curation.models import CuratedDoc, CurationStatus
from src.curation.pipeline import curate_space
from src.db import curated
from src.deps import get_api_key, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/curate", dependencies=[Depends(get_api_key)])


async def _run(space_key: str, threshold: Optional[float]) -> None:
    try:
        logger.info(f"Curation finished: {await curate_space(space_key, threshold)}")
    except Exception:
        logger.exception(f"Curation of space {space_key} failed")


@router.post("/space/{space_key}", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("2/minute")  # type: ignore
async def start_curation(
    request: Request,
    space_key: str,
    background_tasks: BackgroundTasks,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """Cluster duplicates of a backed-up space and produce unified, refined documents."""
    background_tasks.add_task(_run, space_key, threshold)
    return {"message": "Curation accepted", "space_key": space_key}


@router.get("/space/{space_key}")
@limiter.limit("30/minute")  # type: ignore
async def list_docs(
    request: Request, space_key: str, doc_status: Optional[str] = None
) -> Dict[str, Any]:
    """List curated documents, optionally filtered by status (e.g. needs_review)."""
    rows = await curated.list_curated(space_key, doc_status)
    return {"space_key": space_key, "documents": [dict(r) for r in rows]}


@router.get("/doc/{doc_id}", response_model=CuratedDoc)
@limiter.limit("60/minute")  # type: ignore
async def get_doc(request: Request, doc_id: str) -> CuratedDoc:
    doc = await curated.get_curated(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Curated document not found")
    return doc


@router.post("/doc/{doc_id}/approve")
@limiter.limit("30/minute")  # type: ignore
async def approve_doc(request: Request, doc_id: str) -> Dict[str, Any]:
    """Human sign-off: the document is locked against regeneration."""
    if not await curated.set_status(doc_id, CurationStatus.HUMAN_APPROVED):
        raise HTTPException(status_code=404, detail="Curated document not found")
    doc = await curated.get_curated(doc_id)
    if doc is not None:
        export_doc(doc)
    return {"message": "Document approved", "doc_id": doc_id}
