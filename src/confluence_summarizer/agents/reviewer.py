import json
from typing import Optional
from confluence_summarizer.models import ReviewResult, RefinementStatus
from confluence_summarizer.agents.common import generate_response, clean_json_response

async def review(original_text: str, rewritten_text: str) -> Optional[ReviewResult]:
    """Reviews text using the Reviewer Agent."""
    system_prompt = """
    You are an expert Confluence Documentation Quality Assurance Agent.
    Your task is to compare the rewritten documentation against the original to ensure all critiques were addressed,
    no unintended changes were introduced, and no hallucinations were added.

    Provide your response as a JSON object matching this schema:
    {
      "status": "APPROVED", "REJECTED", or "NEEDS_REVISION",
      "comments": "Comments explaining the review decision."
    }
    """

    prompt = f"""
    Compare the rewritten documentation against the original.

    Original Text:
    {original_text}

    Rewritten Text:
    {rewritten_text}
    """

    response_text = await generate_response(prompt, system_prompt)

    if not response_text:
        return None

    try:
        cleaned_json = clean_json_response(response_text)
        data = json.loads(cleaned_json)

        status_str = data.get("status", "").upper()

        # Handle aliases and mapping
        if status_str in ("APPROVED", "ACCEPTED", "COMPLETED"):
            status_str = "COMPLETED"

        # Map to RefinementStatus
        try:
            status = RefinementStatus(status_str)
        except ValueError:
            status = RefinementStatus.NEEDS_REVISION

        data["status"] = status
        return ReviewResult(**data)
    except json.JSONDecodeError:
        return None
    except Exception:
        return None
