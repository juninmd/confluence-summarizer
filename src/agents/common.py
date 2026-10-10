import logging
import re
from typing import Optional

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

_openai_client: Optional[AsyncOpenAI] = None


def _get_client() -> Optional[AsyncOpenAI]:
    global _openai_client
    if _openai_client is None:
        # A self-hosted OpenAI-compatible server (vLLM/Ollama) needs no real key
        if not settings.OPENAI_API_KEY and not settings.LLM_BASE_URL:
            logger.warning("OPENAI_API_KEY not set. LLM capabilities will be disabled.")
            return None
        _openai_client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.OPENAI_API_KEY or "not-needed",
            max_retries=2,
        )
    return _openai_client


async def generate_response(
    prompt: str,
    system_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> str:
    """Helper function to generate a response from OpenAI's Chat API.

    Args:
        prompt (str): The user prompt to send to the model.
        system_prompt (str): The system instruction prompt.
        model (Optional[str]): The LLM model; defaults to settings.LLM_MODEL.
        temperature (float): The generation temperature.

    Returns:
        str: The generated response as a string.
    """
    client = _get_client()
    if client is None:
        logger.warning("Returning mock response due to missing OpenAI client.")
        return (
            '{"critiques": [{"description": "Mock critique due to missing API key.", '
            '"severity": "low", "suggestion": "Fix it."}]}'
        )

    response = await client.chat.completions.create(
        model=model or settings.LLM_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content or ""
    # Reasoning models (e.g. Qwen3) may prepend a <think> block to the answer
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


def clean_json_response(raw_text: str) -> str:
    """Clean markdown code blocks from an LLM JSON response.

    Args:
        raw_text: The raw response text containing JSON.

    Returns:
        The cleaned JSON string.
    """
    match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw_text.strip()
