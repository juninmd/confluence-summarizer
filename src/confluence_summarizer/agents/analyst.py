"""
Analyst Agent
=============
The Analyst Agent is the first step in the refinement pipeline.
It is responsible for reading the raw content extracted from Confluence and identifying issues.

Responsibilities:
- Analyze text for clarity, conciseness, and tone.
- Check for formatting issues (headers, code blocks).
- Identify outdated information (dates, versions).
- output a structured list of critiques.

Input:
- Raw page content.
- Related context (retrieved via RAG).

Output:
- A list of `Critique` objects.
"""

import json
import logging
from typing import List
from ..models import Critique
from .common import call_llm, clean_json_response

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are the Analyst Agent. Your goal is to critique technical documentation.
Identify issues related to clarity, accuracy, formatting, and tone.
Output a JSON object with a key "critiques" containing a list of objects.
Each object must have: "issue_type", "description", "severity" (info, warning, critical), and "suggestion".
"""


async def analyze_content(content: str, context: List[str]) -> List[Critique]:
    """
    Analyzes the content and returns a list of critiques.

    Args:
        content: The raw text content of the page.
        context: A list of related document snippets to help with fact-checking.

    Returns:
        List[Critique]: A list of critiques found in the content.
    """
    context_str = "\n---\n".join(context)
    prompt = f"""
    Analyze the following documentation page.

    CONTEXT (Related pages):
    {context_str}

    PAGE CONTENT:
    {content}
    """

    response = await call_llm(prompt, system_prompt=SYSTEM_PROMPT, json_mode=True)
    if not response:
        raise RuntimeError("Analyst Agent failed to generate a response (empty output).")

    try:
        cleaned_response = clean_json_response(response)
        data = json.loads(cleaned_response)
        critiques_data = data.get("critiques", [])
        # Normalize severity to lowercase to ensure Pydantic validation
        for c in critiques_data:
            if "severity" in c and isinstance(c["severity"], str):
                c["severity"] = c["severity"].lower()
        return [Critique(**c) for c in critiques_data]
    except Exception as e:
        logger.error(f"Error parsing analyst response: {e}\nResponse was: {response}", exc_info=True)
        raise RuntimeError(f"Analyst Agent failed to parse response: {e}")
