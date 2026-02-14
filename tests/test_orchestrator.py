import pytest
from unittest.mock import AsyncMock, patch
from confluence_summarizer.agents import orchestrator
from confluence_summarizer.models import ConfluencePage, RefinementStatus, Critique, IssueSeverity


@pytest.fixture
def mock_rag():
    with patch("confluence_summarizer.agents.orchestrator.rag", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_analyst():
    with patch("confluence_summarizer.agents.orchestrator.analyst", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_writer():
    with patch("confluence_summarizer.agents.orchestrator.writer", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_reviewer():
    with patch("confluence_summarizer.agents.orchestrator.reviewer", new_callable=AsyncMock) as mock:
        yield mock


@pytest.mark.asyncio
async def test_refine_page_no_critiques(mock_rag, mock_analyst):
    mock_rag.query_context.return_value = []
    mock_analyst.analyze_content.return_value = []

    page = ConfluencePage(id="1", title="T", body="B", space_key="S", version=1, url="u")
    result = await orchestrator.refine_page(page)

    assert result.status == RefinementStatus.COMPLETED
    assert result.reviewer_comments == "No critiques found."
    mock_rag.ingest_page.assert_called_once()


@pytest.mark.asyncio
async def test_refine_page_full_flow(mock_rag, mock_analyst, mock_writer, mock_reviewer):
    # Setup context
    context_docs = ["context1", "context2"]
    mock_rag.query_context.return_value = context_docs

    # Setup critique
    critique = Critique(
        issue_type="Clarity",
        description="Vague",
        severity=IssueSeverity.WARNING,
        suggestion="Fix it"
    )
    mock_analyst.analyze_content.return_value = [critique]

    # Setup writer
    mock_writer.rewrite_content.return_value = "Better content"

    # Setup reviewer
    mock_reviewer.review_content.return_value = {
        "status": RefinementStatus.COMPLETED,
        "comments": "Good job"
    }

    page = ConfluencePage(id="1", title="T", body="B", space_key="S", version=1, url="u")
    result = await orchestrator.refine_page(page)

    # Verifications
    assert result.status == RefinementStatus.COMPLETED
    assert result.rewritten_content == "Better content"
    assert len(result.critiques) == 1

    # Verify context was queried and passed
    mock_rag.query_context.assert_called_with("B", exclude_page_id="1")

    # Verify writer received context
    mock_writer.rewrite_content.assert_called_once()
    args = mock_writer.rewrite_content.call_args
    assert args[0][2] == context_docs  # 3rd positional arg is context
