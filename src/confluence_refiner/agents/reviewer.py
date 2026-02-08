"""
Reviewer Agent
==============
The Reviewer Agent is the final step in the refinement pipeline.
It acts as a gatekeeper before content is saved or published.

Responsibilities:
- Validate that the rewritten content is accurate and clear.
- Ensure that the critiques from the Analyst Agent were addressed.
- Check for hallucinations or new errors introduced by the Writer.
- Provide a final status (COMPLETED/REJECTED) and comments.

Input:
- Original content.
- Rewritten content.
- Summary of critiques.

Output:
- A decision status and comments.
"""

import json
import logging
from typing import Dict, Any
from ..models import RefinementStatus
from .common import call_llm, clean_json_response

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are the Reviewer Agent. Validate if the rewritten content is acceptable.
Check if critiques were addressed and if no new errors were introduced.
Output a JSON object with "status" (must be one of: "completed", "rejected") and "comments" (string).
"""


async def review_content(original: str, rewritten: str, critiques_summary: str) -> Dict[str, Any]:
    """
    Reviews the rewritten content against the original and the critiques.

    Args:
        original: The original content.
        rewritten: The rewritten content.
        critiques_summary: A summary of the critiques that were supposed to be addressed.

    Returns:
        Dict[str, Any]: A dictionary containing "status" (RefinementStatus) and "comments" (str).
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
    if not response:
        return {"status": RefinementStatus.FAILED, "comments": "No response from LLM"}

    try:
        cleaned_response = clean_json_response(response)
        data = json.loads(cleaned_response)
        # Normalize status
        status_str = data.get("status", "").lower()
        if status_str == "completed":
            status = RefinementStatus.COMPLETED
        else:
            status = RefinementStatus.REJECTED

        return {"status": status, "comments": data.get("comments", "")}
    except Exception as e:
        logger.error(f"Error parsing reviewer response: {e}\nResponse was: {response}", exc_info=True)
        return {"status": RefinementStatus.FAILED, "comments": "Failed to parse reviewer output"}
