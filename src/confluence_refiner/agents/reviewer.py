import json
from typing import Dict, Any
from ..models import RefinementStatus
from .common import call_llm

SYSTEM_PROMPT = """
You are the Reviewer Agent. Validate if the rewritten content is acceptable.
Check if critiques were addressed and if no new errors were introduced.
Output a JSON object with "status" (must be one of: "completed", "rejected") and "comments" (string).
"""


async def review_content(original: str, rewritten: str, critiques_summary: str) -> Dict[str, Any]:
    """
    Reviews the rewritten content.
    """
    prompt = f"""
    Original Content:
    {original}

    Critiques that were raised:
    {critiques_summary}

    Rewritten Content:
    {rewritten}

    Provide your review.
    """

    response = await call_llm(prompt, system_prompt=SYSTEM_PROMPT, json_mode=True)
    try:
        data = json.loads(response)
        # Normalize status
        status_str = data.get("status", "").lower()
        if status_str == "completed":
            status = RefinementStatus.COMPLETED
        else:
            status = RefinementStatus.REJECTED

        return {"status": status, "comments": data.get("comments", "")}
    except Exception as e:
        print(f"Error parsing reviewer response: {e}")
        return {"status": RefinementStatus.FAILED, "comments": "Failed to parse reviewer output"}
