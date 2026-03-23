from typing import List

from src.confluence_summarizer.agents.common import generate_response
from src.confluence_summarizer.models.domain import AnalysisResult


async def rewrite_content(
    original_text: str, critiques: AnalysisResult, context: List[str]
) -> str:
    """Rewrite the content based on critiques and context."""

    system_prompt = (
        "You are a Writer Agent. Your task is to rewrite the provided Confluence documentation "
        "incorporating the provided critiques and ensuring it is consistent with the provided context. "
        "Return ONLY the rewritten markdown text, without any introductory or concluding remarks."
    )

    critiques_str = "\n".join(
        [
            f"- {c.severity.upper()}: {c.description} -> Suggestion: {c.suggestion}"
            for c in critiques.critiques
        ]
    )

    context_str = "\n".join(
        [f"Context Block {i + 1}: {ctx}" for i, ctx in enumerate(context)]
    )

    prompt = (
        f"Original Text:\n{original_text}\n\n"
        f"Critiques from Analyst:\n{critiques_str}\n\n"
        f"Context from RAG:\n{context_str}\n\n"
        "Please rewrite the document."
    )

    response = await generate_response(prompt=prompt, system_prompt=system_prompt)
    if not response:
        raise ValueError("Writer agent returned an empty response.")
    return response.strip()
