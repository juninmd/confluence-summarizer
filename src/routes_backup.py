"""HTTP endpoints for the Confluence backup."""

import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from src.backup import layout
from src.backup.runner import backup_space
from src.backup.verify import verify_space
from src.deps import get_api_key, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", dependencies=[Depends(get_api_key)])
_running: set[str] = set()


def _checked(space_key: str) -> str:
    try:
        layout.space_dir(space_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return space_key


async def _run(space_key: str, index: bool) -> None:
    try:
        manifest = await backup_space(space_key, index=index)
        logger.info(
            f"Backup of {space_key} finished: {manifest['backed_up_pages']} pages"
        )
    except Exception:
        logger.exception(f"Backup of space {space_key} failed")
    finally:
        _running.discard(space_key)


@router.post("/space/{space_key}", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("2/minute")  # type: ignore
async def start_backup(
    request: Request,
    space_key: str,
    background_tasks: BackgroundTasks,
    index: bool = True,
) -> Dict[str, Any]:
    """Start a full (incremental) backup of a space: raw, Markdown, images, pgvector."""
    _checked(space_key)
    if space_key in _running:
        raise HTTPException(
            status_code=409, detail="Backup already running for this space"
        )
    _running.add(space_key)
    background_tasks.add_task(_run, space_key, index)
    return {"message": "Backup accepted", "space_key": space_key}


@router.get("/space/{space_key}")
@limiter.limit("30/minute")  # type: ignore
async def backup_status(request: Request, space_key: str) -> Dict[str, Any]:
    """Return the manifest summary of the last backup."""
    manifest = layout.load_manifest(layout.space_dir(_checked(space_key)))
    if not manifest.get("pages"):
        raise HTTPException(status_code=404, detail="No backup found")
    pages = manifest["pages"]
    return {
        **{k: v for k, v in manifest.items() if k != "pages"},
        "running": space_key in _running,
        "total_pages": len(pages),
        "deleted_pages": sum(1 for p in pages.values() if p.get("deleted")),
    }


@router.get("/space/{space_key}/verify")
@limiter.limit("5/minute")  # type: ignore
async def backup_verify(request: Request, space_key: str) -> Dict[str, Any]:
    """Verify files, links, images and checksums of the backup."""
    problems = await asyncio.to_thread(verify_space, _checked(space_key))
    return {"space_key": space_key, "ok": not problems, "problems": problems}
