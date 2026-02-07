from typing import List, Optional
from ..models import Critique
from .common import call_llm

SYSTEM_PROMPT = """
You are the Writer Agent. Rewrite the documentation to address the critiques provided.
Maintain the technical accuracy but improve style and formatting.
If related context is provided, use it to ensure consistency and correctness.
Output only the rewritten Markdown content. Do not include preamble or explanation.
"""


async def rewrite_content(original_content: str, critiques: List[Critique], context: Optional[List[str]] = None) -> str:
    """
    Rewrites the content based on critiques and available context.
    """
    if context is None:
        context = []

    critiques_list = [
        f"- [{c.severity}] {c.issue_type}: {c.description}. Suggestion: {c.suggestion}"
        for c in critiques
    ]
    critiques_str = "\n".join(critiques_list)

    context_str = "\n---\n".join(context) if context else "No context provided."

    prompt = f"""
    Original Content:
    {original_content}

    CONTEXT (Related pages):
    {context_str}

    Critiques to Address:
    {critiques_str}

    Rewrite the content:
    """

    return await call_llm(prompt, system_prompt=SYSTEM_PROMPT)
