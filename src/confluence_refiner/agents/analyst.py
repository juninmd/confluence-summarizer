import json
from typing import List
from ..models import Critique
from .common import call_llm

SYSTEM_PROMPT = """
You are the Analyst Agent. Your goal is to critique technical documentation.
Identify issues related to clarity, accuracy, formatting, and tone.
Output a JSON object with a key "critiques" containing a list of objects.
Each object must have: "issue_type", "description", "severity" (info, warning, critical), and "suggestion".
"""


async def analyze_content(content: str, context: List[str]) -> List[Critique]:
    """
    Analyzes the content and returns a list of critiques.
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
        return []

    try:
        data = json.loads(response)
        critiques_data = data.get("critiques", [])
        return [Critique(**c) for c in critiques_data]
    except Exception as e:
        print(f"Error parsing analyst response: {e}")
        return []
