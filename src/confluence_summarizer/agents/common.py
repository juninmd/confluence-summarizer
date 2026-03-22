import re

import logging
from typing import Optional
from openai import AsyncOpenAI
from src.confluence_summarizer.config import settings

logger = logging.getLogger(__name__)

_openai_client: Optional[AsyncOpenAI] = None

def _get_client() -> Optional[AsyncOpenAI]:
    """Lazy init of OpenAI client. Logs warning if missing API KEY to support CI."""
    global _openai_client
    if _openai_client is None:
        if not settings.openai_api_key or settings.openai_api_key == "sk-dummy":
            logger.warning("OPENAI_API_KEY ausente ou dummy. LLM capabilities will be disabled.")
            return None
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client

def clean_json_response(raw_text: str) -> str:
    """Strippa potenciais blocos markdown de código ```json ... ``` retornados pelo LLM para parse valid."""
    cleaned = re.sub(r"^```json", "", raw_text, flags=re.MULTILINE)
    cleaned = re.sub(r"^```", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()

async def generate_response(system_prompt: str, user_prompt: str) -> str:
    """Helper genérico para solicitar respostas assíncronas do gpt-4-turbo-preview para agentes."""
    client = _get_client()
    if client is None:
         return "{}"

    response = await client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3
    )

    content = response.choices[0].message.content
    return content if content else "{}"
