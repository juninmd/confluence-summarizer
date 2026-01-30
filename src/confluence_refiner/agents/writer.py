from typing import List
from ..models import Critique
from .common import call_llm

SYSTEM_PROMPT = """
You are the Writer Agent. Rewrite the documentation to address the critiques provided.
Maintain the technical accuracy but improve style and formatting.
Output only the rewritten Markdown content. Do not include preamble or explanation.
"""


async def rewrite_content(original_content: str, critiques: List[Critique]) -> str:
    """
    Rewrites the content based on critiques.
    """
    critiques_list = [
        f"- [{c.severity}] {c.issue_type}: {c.description}. Suggestion: {c.suggestion}"
        for c in critiques
    ]
    critiques_str = "\n".join(critiques_list)

    prompt = f"""
    Original Content:
    {original_content}

    Critiques to Address:
    {critiques_str}

    Rewrite the content:
    """

    return await call_llm(prompt, system_prompt=SYSTEM_PROMPT)
