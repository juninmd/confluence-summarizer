import pytest
import json
from src.confluence_summarizer.agents.common import clean_json_response, _get_client
from src.confluence_summarizer.agents.analyst import analyze_page
from src.confluence_summarizer.agents.writer import rewrite_page
from src.confluence_summarizer.agents.reviewer import review_page
from src.confluence_summarizer.models.domain import RefinementStatus
from src.confluence_summarizer.config import settings

def test_clean_json_response():
    """Valida strip de markdown wrappers retornados por LLMs."""
    raw = "```json\n{\"foo\":\"bar\"}\n```"
    assert clean_json_response(raw) == '{"foo":"bar"}'

@pytest.mark.asyncio
async def test_analyze_page_success(mocker):
    """Garante normalização de severity lowercase pelo Analyst agent."""
    mock_llm_response = json.dumps({
        "critiques": [
            {"issue": "Sem título", "severity": "HIGH", "suggestion": "Adicionar"}
        ]
    })
    mocker.patch("src.confluence_summarizer.agents.analyst.generate_response", return_value=mock_llm_response)

    response = await analyze_page("<html><body>Sem título</body></html>")
    assert response.critiques[0].severity == "high"

@pytest.mark.asyncio
async def test_writer_page_success(mocker):
    """Testa geração HTML a partir de feedback pelo Writer."""
    mocker.patch("src.confluence_summarizer.agents.writer.generate_response", return_value="<html>Melhorado</html>")

    mock_critiques = type("MockAnalyst", (), {"critiques": []})()
    res = await rewrite_page("<html>Antigo</html>", mock_critiques, ["context 1"])
    assert res == "<html>Melhorado</html>"

@pytest.mark.asyncio
async def test_review_page_status_normalization(mocker):
    """Verifica aliás cases no Reviewer."""
    mocker.patch("src.confluence_summarizer.agents.reviewer.generate_response", return_value='{"status": "Completed", "feedback": "Ok"}')
    res = await review_page("A", "B")
    assert res.status == RefinementStatus.COMPLETED.value

    mocker.patch("src.confluence_summarizer.agents.reviewer.generate_response", return_value='{"status": "Bad", "feedback": "Fail"}')
    res_fail = await review_page("A", "B")
    assert res_fail.status == RefinementStatus.REJECTED.value

def test_missing_openai_key_disables_client():
    """Valida bypass e desabilitação em CI environment sem chaves reais."""
    original_key = settings.openai_api_key
    settings.openai_api_key = ""
    client = _get_client()
    assert client is None
    settings.openai_api_key = original_key
