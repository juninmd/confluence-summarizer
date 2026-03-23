import json
from typing import List

from pydantic import ValidationError

from confluence_summarizer.models import Critique
from confluence_summarizer.agents.common import generate_response, clean_json_response

system_message = """
You are an expert Technical Writer and Analyst. Your job is to review documentation content and identify:
1. Contradictions or confusing statements
2. Poor formatting or structure
3. Missing technical context
4. Outdated information

Analyze the given Confluence page content and return a JSON list of critiques. Each critique MUST have the following schema:
{
    "critiques": [
        {
            "issue": "Description of the issue",
            "severity": "high/medium/low",
            "suggestion": "How to fix it"
        }
    ]
}

Make sure the JSON is valid and only use high, medium, or low for severity. Do not include markdown formatting.
"""


async def analyze_page(content: str) -> List[Critique]:
    prompt = f"Analyze the following content:\n\n{content}"
    response = await generate_response(prompt, system_message, response_format="json_object")

    cleaned = clean_json_response(response)

    try:
        data = json.loads(cleaned)
        critiques_data = data.get("critiques", [])

        critiques = []
        for item in critiques_data:
            # Normalize severity
            item["severity"] = str(item.get("severity", "low")).lower()
            try:
                critiques.append(Critique(**item))
            except ValidationError:
                continue

        return critiques
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Analyst response as JSON: {e}")
