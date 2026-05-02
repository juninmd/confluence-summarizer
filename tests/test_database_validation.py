import pytest

from src.confluence_summarizer.database import save_job_sync
from src.confluence_summarizer.models.domain import RefinementJob, RefinementStatus


def test_save_job_sync_missing_id():
    job = RefinementJob(
        id="",
        page_id="page-123",
        status=RefinementStatus.PENDING,
    )
    with pytest.raises(ValueError, match="Job id is required"):
        save_job_sync(job)


def test_save_job_sync_missing_page_id():
    job = RefinementJob(
        id="job-123",
        page_id="",
        status=RefinementStatus.PENDING,
    )
    with pytest.raises(ValueError, match="Job page_id is required"):
        save_job_sync(job)


def test_save_job_sync_invalid_status():
    # We bypass Pydantic's init validation to test the DB logic
    job = RefinementJob.model_construct(
        id="job-123",
        page_id="page-123",
        status="invalid_status",  # type: ignore
        error=None,
        original_text=None,
        refined_text=None,
    )

    with pytest.raises(ValueError, match="Job status must be a valid RefinementStatus"):
        save_job_sync(job)


def test_save_job_sync_missing_status():
    job = RefinementJob.model_construct(
        id="job-123",
        page_id="page-123",
        status=None,  # type: ignore
        error=None,
        original_text=None,
        refined_text=None,
    )

    with pytest.raises(ValueError, match="Job status must be a valid RefinementStatus"):
        save_job_sync(job)
