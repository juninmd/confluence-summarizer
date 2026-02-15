import os
import logging
import re
from typing import Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: Optional[AsyncOpenAI] = None


def _get_client() -> Optional[AsyncOpenAI]:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set. LLM calls will fail.")
            return None
        try:
            _client = AsyncOpenAI(api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            return None
    return _client


def clean_json_response(response: str) -> str:
    """
    Cleans the LLM response to ensure it is valid JSON.
    Removes Markdown code blocks (```json ... ```) using regex.
    """
    # Regex to find content within ```json ... ``` or just ``` ... ```
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return response.strip()


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
    if not client:
        logger.error("Cannot call LLM: Client not initialized (missing API key?)")
        return ""

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
