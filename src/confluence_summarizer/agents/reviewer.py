import json
from src.confluence_summarizer.agents.common import (
    generate_response,
    clean_json_response,
)
from src.confluence_summarizer.models.domain import RefinementStatus, AnalysisResult
from pydantic import BaseModel, Field


class ReviewResult(BaseModel):
    status: RefinementStatus = Field(
        description="Review decision (accepted, pending, failed)."
    )
    feedback: str = Field(description="Optional feedback.")


async def review_content(
    original_text: str, rewritten_text: str, critiques: AnalysisResult
) -> ReviewResult:
    """Review the rewritten content against the original and critiques."""

    system_prompt = (
        "You are a Reviewer Agent. Your task is to evaluate the rewritten Confluence documentation "
        "against the original text and the Analyst's critiques. Ensure the rewritten text is coherent, "
        "factually correct, and has properly addressed the critiques. "
        "Respond in JSON format with two keys: 'status' (can be 'completed', 'accepted', 'approved', 'failed', 'pending') "
        "and 'feedback' (string detailing your decision)."
    )

    critiques_str = "\n".join(
        [f"- {c.severity.upper()}: {c.description}" for c in critiques.critiques]
    )

    prompt = (
        f"Original Text:\n{original_text}\n\n"
        f"Rewritten Text:\n{rewritten_text}\n\n"
        f"Analyst Critiques:\n{critiques_str}\n\n"
        "Please provide your review in JSON format."
    )

    response = await generate_response(prompt=prompt, system_prompt=system_prompt)
    cleaned_json = clean_json_response(response)

    try:
        data = json.loads(cleaned_json)
        status_str = data.get("status", "pending").lower()
        if status_str in ["accepted", "approved", "completed"]:
            status = RefinementStatus.COMPLETED
        elif status_str == "failed":
            status = RefinementStatus.FAILED
        else:
            status = RefinementStatus.PENDING

        return ReviewResult(status=status, feedback=data.get("feedback", ""))
    except Exception as e:
        return ReviewResult(
            status=RefinementStatus.FAILED, feedback=f"Failed to parse review: {e}"
        )
