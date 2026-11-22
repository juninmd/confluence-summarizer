import httpx
import pytest
from tenacity import wait_none

from src.config import settings
from src.services import confluence

PUT_URL = f"{settings.CONFLUENCE_URL}/wiki/api/v2/pages/123"


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr(confluence.update_page.retry, "wait", wait_none())
    confluence._client = None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome",
    [httpx.ReadTimeout("lost response"), httpx.Response(502), httpx.Response(500)],
)
async def test_update_is_not_resent_when_the_server_may_have_applied_it(respx_mock, outcome):
    # Resending the same version after a commit makes Confluence answer 409:
    # a published page would be reported as a failure.
    route = respx_mock.put(PUT_URL).mock(side_effect=[outcome, httpx.Response(409)])
    with pytest.raises((httpx.ReadTimeout, httpx.HTTPStatusError)) as exc:
        await confluence.update_page("123", "T", "B", 2)
    assert route.call_count == 1
    if isinstance(exc.value, httpx.HTTPStatusError):
        assert exc.value.response.status_code != 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first", [httpx.ConnectError("refused"), httpx.ConnectTimeout("slow"), httpx.Response(429)]
)
async def test_update_is_retried_when_it_never_reached_confluence(respx_mock, first):
    route = respx_mock.put(PUT_URL).mock(side_effect=[first, httpx.Response(200, json={"ok": 1})])
    assert await confluence.update_page("123", "T", "B", 2) == {"ok": 1}
    assert route.call_count == 2
