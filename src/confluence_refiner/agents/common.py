import os
from openai import AsyncOpenAI

# Initialize OpenAI client
# Assuming OPENAI_API_KEY is set in environment
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-mock-key-for-testing"))


async def call_llm(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str = "gpt-4-turbo-preview",
    json_mode: bool = False
) -> str:
    """
    Calls the LLM with the given prompt.
    """

    # Construct arguments explicitly to avoid Pyright errors with unpacking dicts
    # into typed parameters.

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

        return response.choices[0].message.content or ""
    except Exception as e:
        # In a real app we'd log this better
        print(f"Error calling LLM: {e}")
        return ""
