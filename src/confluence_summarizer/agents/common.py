import os
import logging
from typing import Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        # We allow api_key to be None here (OpenAI lib might raise later, or we check it)
        # But this prevents import-time crashes.
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set. LLM calls will fail.")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


def clean_json_response(response: str) -> str:
    """
    Cleans the LLM response to ensure it is valid JSON.
    Removes Markdown code blocks (```json ... ```).
    """
    cleaned = response.strip()
    if cleaned.startswith("```"):
        # Remove first line (```json or ```)
        cleaned = cleaned.split("\n", 1)[1]
        # Remove last line (```)
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
    return cleaned.strip()


async def call_llm(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str = "gpt-4-turbo-preview",
    json_mode: bool = False
) -> str:
    """
    Calls the LLM with the given prompt.
    """
    client = _get_client()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    try:
        if json_mode:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore
                response_format={"type": "json_object"}
            )
        else:
            response = await client.chat.completions.create(
                model=model,
                messages=messages  # type: ignore
            )

        content = response.choices[0].message.content or ""
        return content
    except Exception as e:
        logger.error(f"Error calling LLM: {e}", exc_info=True)
        return ""
