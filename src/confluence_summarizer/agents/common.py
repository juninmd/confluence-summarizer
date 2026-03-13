import logging
import re
from typing import Optional
from openai import AsyncOpenAI
from src.confluence_summarizer.config import settings

logger = logging.getLogger(__name__)

_openai_client: Optional[AsyncOpenAI] = None


def _get_client() -> Optional[AsyncOpenAI]:
    global _openai_client
    if _openai_client is None:
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set. LLM capabilities will be disabled.")
            return None
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


async def generate_response(
    prompt: str,
    system_prompt: str,
    model: str = "gpt-4-turbo-preview",
    temperature: float = 0.7,
) -> str:
    """Helper function to generate a response from OpenAI's Chat API."""
    client = _get_client()
    if client is None:
        logger.warning("Returning mock response due to missing OpenAI client.")
        return '{"critiques": [{"description": "Mock critique due to missing API key.", "severity": "low", "suggestion": "Fix it."}]}'

    response = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content
    return content if content else ""


def clean_json_response(raw_text: str) -> str:
    """Clean markdown code blocks from an LLM JSON response."""
    match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw_text.strip()
