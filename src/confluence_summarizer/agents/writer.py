from typing import List, Optional
from confluence_summarizer.models import AnalysisResult
from confluence_summarizer.agents.common import generate_response

async def rewrite(text: str, analysis: AnalysisResult, context: List[str]) -> Optional[str]:
    """Rewrites text using the Writer Agent."""
    system_prompt = """
    You are an expert Confluence Documentation Writer Agent.
    Your task is to rewrite and refine the provided documentation.
    You must use the original text, the Analyst's critique, and the retrieved context (RAG)
    to ensure factual consistency, standardization, and clarity.

    Do not introduce contradictions or hallucinations. Focus on clarity and consistency.
    Output only the rewritten text in Confluence Storage Format (HTML/XML).
    """

    critiques_text = "\n".join(
        [f"- {c.finding} (Severity: {c.severity}) -> {c.recommendation}" for c in analysis.critiques]
    )
    context_text = "\n\n---\n\n".join(context) if context else "No additional context available."

    prompt = f"""
    Rewrite the following Confluence page content based on the critiques and context.

    Original Text:
    {text}

    Analyst Critiques:
    {critiques_text}

    Retrieved Context (for cross-checking facts):
    {context_text}
    """

    response_text = await generate_response(prompt, system_prompt)
    return response_text
