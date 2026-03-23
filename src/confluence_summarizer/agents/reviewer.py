import json
from typing import List, Tuple

from confluence_summarizer.models import Critique, RefinementStatus
from confluence_summarizer.agents.common import generate_response, clean_json_response

system_message = """
You are the Quality Assurance (QA) Technical Reviewer. Your role is to evaluate whether a final documentation draft successfully addresses all critiques from the Analyst.
The original content is provided alongside the final draft.

You must output valid JSON without markdown wrapping.

The response schema must be exactly:
{
    "status": "accepted/rejected/completed/approved",
    "feedback": "Why it was accepted or rejected"
}
"""


async def review_page(
    original_content: str, final_draft: str, critiques: List[Critique]
) -> Tuple[RefinementStatus, str]:
    critiques_text = "\n".join([f"- {c.severity.upper()}: {c.issue}" for c in critiques])

    prompt = f"""
ORIGINAL CONTENT:
{original_content}

CRITIQUES:
{critiques_text}

FINAL DRAFT:
{final_draft}

Does the final draft address the critiques and keep the meaning intact?
"""

    response = await generate_response(prompt, system_message, response_format="json_object")
    cleaned = clean_json_response(response)

    try:
        data = json.loads(cleaned)
        status_str = str(data.get("status", "rejected")).lower()
        feedback = data.get("feedback", "No feedback provided")

        if status_str in ["approved", "completed", "accepted"]:
            status = RefinementStatus.COMPLETED
        else:
            status = RefinementStatus.FAILED

        return status, feedback

    except json.JSONDecodeError as e:
        raise RuntimeError(f"Reviewer failed to output valid JSON: {e}")
