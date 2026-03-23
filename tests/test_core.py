import pytest
from confluence_summarizer.agents.common import clean_json_response
from confluence_summarizer.agents.analyst import analyze_page
from confluence_summarizer.agents.reviewer import review_page
from confluence_summarizer.models import Critique, RefinementStatus


def test_clean_json_response():
    raw_json = '```json\n{"test": 123}\n```'
    assert clean_json_response(raw_json) == '{"test": 123}'

    raw_text = '{"test": 123}'
    assert clean_json_response(raw_text) == '{"test": 123}'


@pytest.mark.asyncio
async def test_analyze_page_success(monkeypatch):
    async def mock_generate_response(*args, **kwargs):
        return """
        {
            "critiques": [
                {
                    "issue": "Bad format",
                    "severity": "HIGH",
                    "suggestion": "Fix it"
                }
            ]
        }
        """

    monkeypatch.setattr("confluence_summarizer.agents.analyst.generate_response", mock_generate_response)

    critiques = await analyze_page("Some content")
    assert len(critiques) == 1
    assert critiques[0].issue == "Bad format"
    assert critiques[0].severity == "high"  # Normalized to lowercase


@pytest.mark.asyncio
async def test_review_page_success(monkeypatch):
    async def mock_generate_response(*args, **kwargs):
        return """
        {
            "status": "completed",
            "feedback": "Looks good"
        }
        """

    monkeypatch.setattr("confluence_summarizer.agents.reviewer.generate_response", mock_generate_response)

    critique = Critique(issue="Bad format", severity="high", suggestion="Fix it")
    status, feedback = await review_page("Old", "New", [critique])

    assert status == RefinementStatus.COMPLETED
    assert feedback == "Looks good"


@pytest.mark.asyncio
async def test_review_page_rejected(monkeypatch):
    async def mock_generate_response(*args, **kwargs):
        return """
        {
            "status": "rejected",
            "feedback": "Needs work"
        }
        """

    monkeypatch.setattr("confluence_summarizer.agents.reviewer.generate_response", mock_generate_response)

    critique = Critique(issue="Bad format", severity="high", suggestion="Fix it")
    status, feedback = await review_page("Old", "New", [critique])

    assert status == RefinementStatus.FAILED
    assert feedback == "Needs work"
