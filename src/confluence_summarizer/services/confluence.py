import logging
import urllib.parse
from typing import Dict, Any, List, Optional
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt
from src.confluence_summarizer.config import settings

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None

def init_client() -> None:
    """Inicializa o HTTP client para a Confluence API de forma idempotente."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30.0)

async def close_client() -> None:
    """Fecha de modo seguro e idempotente o AsyncClient caso esteja instanciado."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None

def _get_auth() -> Optional[httpx.BasicAuth]:
    """Retorna a autenticação HTTP Basic baseada no arquivo .env."""
    if not settings.confluence_username or not settings.confluence_api_token:
        logger.warning("Credenciais do Confluence ausentes. Conexão HTTP pode falhar.")
        return None
    return httpx.BasicAuth(settings.confluence_username, settings.confluence_api_token)

def _get_http_client() -> httpx.AsyncClient:
    """Helper interno para obter o client global instanciado ou retornar um error (na prática cria um novo caso o lifespan falhe)."""
    global _client
    if _client is None:
        logger.warning("Shared client not initialized! Using a fallback client (may degrade connection pooling).")
        return httpx.AsyncClient(timeout=30.0)
    return _client

@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
async def get_page_by_id(page_id: str) -> Dict[str, Any]:
    """Recupera o conteúdo completo e propriedades de uma página através de seu ID."""
    safe_page_id = urllib.parse.quote(page_id)
    url = f"{settings.confluence_url}/wiki/api/v2/pages/{safe_page_id}?body-format=storage"

    client = _get_http_client()
    auth = _get_auth()
    # Se autenticação falhar de setup retorna vazio ou propaga erro do endpoint
    response = await client.get(url, auth=auth)
    response.raise_for_status()
    return response.json()

@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
async def get_pages_in_space(space_key: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Recupera todas as páginas do Space especificado com chunk de paginação limitando iterativamente."""
    safe_space_key = urllib.parse.quote(space_key)
    base_url = f"{settings.confluence_url}/wiki/api/v2/spaces/{safe_space_key}/pages?body-format=storage&limit={limit}"

    client = _get_http_client()
    auth = _get_auth()

    pages: List[Dict[str, Any]] = []
    next_link: str | None = base_url

    while next_link:
        if not next_link.startswith("http"):
             # Confluence API v2 often returns relative paths for 'next'
             next_link = f"{settings.confluence_url}{next_link}"

        response = await client.get(next_link, auth=auth)
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        pages.extend(results)

        # Paginação
        links = data.get("_links", {})
        next_path = links.get("next")
        if next_path:
             next_link = next_path
        else:
             next_link = None

    return pages
