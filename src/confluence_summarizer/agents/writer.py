"""
Writer Agent
============
The Writer Agent is the second step in the refinement pipeline.
It takes the critiques from the Analyst Agent and the original content to produce a refined version.

Responsibilities:
- Rewrite the documentation to address all critiques.
- Improve clarity, conciseness, and tone.
- Ensure factual consistency by using the provided context.
- Maintain the original logical structure unless confusing.
- Format code blocks and headers correctly.

Input:
- Original content.
- List of critiques.
- Related context (RAG).

Output:
- The rewritten Markdown content.
"""

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

    Args:
        original_content: The original page content.
        critiques: A list of critiques identified by the Analyst Agent.
        context: Optional list of related documents for context.

    Returns:
        str: The rewritten content in Markdown format.
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

    response = await call_llm(prompt, system_prompt=SYSTEM_PROMPT)
    if not response:
        raise RuntimeError("Writer Agent failed to rewrite content (empty output).")
    return response
