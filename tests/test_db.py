import pytest
import os
import asyncio
from confluence_summarizer.database import init_db, save_job, get_job
from confluence_summarizer.models import RefinementResult, RefinementStatus

# Use a separate DB for testing
TEST_DB_PATH = "test_jobs.db"


@pytest.fixture
def test_db():
    # Patch DB_PATH in the db module
    import confluence_summarizer.database as db_module
    old_path = db_module.DB_PATH
    db_module.DB_PATH = TEST_DB_PATH

    # Run init
    asyncio.run(init_db())

    yield

    # Cleanup
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    db_module.DB_PATH = old_path


@pytest.mark.asyncio
async def test_db_persistence(test_db):
    job = RefinementResult(
        page_id="test_1",
        original_content="content",
        status=RefinementStatus.PENDING
    )

    await save_job(job)

    loaded = await get_job("test_1")
    assert loaded is not None
    assert loaded.page_id == "test_1"
    assert loaded.status == RefinementStatus.PENDING


@pytest.mark.asyncio
async def test_get_job_missing(test_db):
    loaded = await get_job("missing")
    assert loaded is None


@pytest.mark.asyncio
async def test_update_job(test_db):
    job = RefinementResult(
        page_id="test_2",
        original_content="content",
        status=RefinementStatus.PROCESSING
    )
    await save_job(job)

    job.status = RefinementStatus.COMPLETED
    await save_job(job)

    loaded = await get_job("test_2")
    assert loaded is not None
    assert loaded.status == RefinementStatus.COMPLETED
