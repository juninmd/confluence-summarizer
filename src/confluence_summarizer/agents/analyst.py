import json
from typing import List

import pydantic

from src.confluence_summarizer.agents.common import (
    clean_json_response,
    generate_response,
)
from src.confluence_summarizer.models.domain import AnalysisResult


async def analyze_content(original_text: str, context: List[str]) -> AnalysisResult:
    """Analyze the content against the given context to identify flaws.

    Args:
        original_text (str): The original Confluence documentation text.
        context (List[str]): Context text retrieved from the vector database.

    Returns:
        AnalysisResult: An AnalysisResult object containing the generated critiques.
    """

    system_prompt = (
        "You are an Analyst Agent. Your task is to review the provided Confluence documentation text "
        "and compare it against the provided context. Identify any flaws, outdated information, formatting issues, "
        "or inconsistencies. Provide a list of critiques in a structured JSON format matching this schema:\n"
        '{"critiques": [{"description": "Issue description", "severity": "low|medium|high", '
        '"suggestion": "How to fix"}]}'
    )

    context_str = "\n".join(
        [f"Context Block {i + 1}: {ctx}" for i, ctx in enumerate(context)]
    )
    prompt = (
        f"Original Text:\n{original_text}\n\n"
        f"Context from RAG:\n{context_str}\n\n"
        "Please provide the critiques in JSON format."
    )

    response = await generate_response(prompt=prompt, system_prompt=system_prompt)
    cleaned_json = clean_json_response(response)

    try:
        data = json.loads(cleaned_json)
        # Normalize severity to lowercase to ensure Pydantic validation passes
        if "critiques" in data:
            for critique in data["critiques"]:
                if "severity" in critique and isinstance(critique["severity"], str):
                    critique["severity"] = critique["severity"].lower()

        return AnalysisResult(**data)
    except (
        json.JSONDecodeError,
        pydantic.ValidationError,
        KeyError,
        TypeError,
        AttributeError,
    ):
        # Fallback empty result
        return AnalysisResult(critiques=[])
