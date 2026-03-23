from typing import List

from confluence_summarizer.models import Critique
from confluence_summarizer.agents.common import generate_response

system_message = """
You are a Staff Software Engineer and Documentation Writer.
Your task is to re-write a Confluence page to address the critiques provided by the Analyst, while maintaining consistency with the broader space context.

Guidelines:
1. Retain any HTML formatting/structure (like macros or macros-like structure) unless it needs to be corrected.
2. Incorporate factual corrections from the RAG context.
3. Ensure the tone is professional, technical, and clear.
4. Output ONLY the rewritten content without markdown code blocks.
"""


async def rewrite_page(original_content: str, critiques: List[Critique], context_chunks: List[str]) -> str:
    critiques_text = "\n".join([f"- {c.severity.upper()}: {c.issue}\n  Suggestion: {c.suggestion}" for c in critiques])
    context_text = "\n\n".join(context_chunks) if context_chunks else "No additional context available."

    prompt = f"""
ORIGINAL CONTENT:
{original_content}

CRITIQUES TO ADDRESS:
{critiques_text}

RAG CONTEXT (use this to fix factual inconsistencies):
{context_text}

Write the final updated content:
"""
    return await generate_response(prompt, system_message, response_format="text")
