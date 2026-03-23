import logging
import re
from typing import Optional

from openai import AsyncOpenAI

from confluence_summarizer.config import settings

logger = logging.getLogger(__name__)

_openai_client: Optional[AsyncOpenAI] = None


def _get_client() -> Optional[AsyncOpenAI]:
    global _openai_client
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "dummy-openai-key":
        logger.warning("Missing OpenAI API Key. LLM capabilities will be disabled.")
        return None

    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    return _openai_client


async def generate_response(
    prompt: str, system_message: str, model: str = "gpt-4-turbo-preview", response_format: str = "text"
) -> str:
    client = _get_client()
    if client is None:
        raise RuntimeError("OpenAI Client is not initialized.")

    messages = [{"role": "system", "content": system_message}, {"role": "user", "content": prompt}]

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
    }

    if response_format == "json_object":
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Empty response from LLM")

    return content


def clean_json_response(response: str) -> str:
    # Strip markdown code blocks like ```json ... ```
    cleaned = re.sub(r"```json\s*", "", response)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    return cleaned.strip()
