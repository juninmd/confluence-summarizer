import os
import logging
from typing import Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: Optional[AsyncOpenAI] = None

def _get_client() -> Optional[AsyncOpenAI]:
    """Returns the OpenAI client, or None if the API key is missing."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY is not set. LLM capabilities will be disabled.")
            return None
        _client = AsyncOpenAI(api_key=api_key)
    return _client

def clean_json_response(response: str) -> str:
    """Removes Markdown code block formatting from LLM outputs."""
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]

    if response.endswith("```"):
        response = response[:-3]

    return response.strip()

async def generate_response(
    prompt: str, system_prompt: str = "You are a helpful assistant.", model: str = "gpt-4-turbo-preview"
) -> Optional[str]:
    """Generates a response from the LLM."""
    client = _get_client()
    if not client:
        return None

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # Lower temperature for more factual outputs
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        return None
