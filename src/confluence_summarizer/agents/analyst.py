import json
from typing import Optional
from confluence_summarizer.models import AnalysisResult
from confluence_summarizer.agents.common import generate_response, clean_json_response


async def analyze(text: str) -> Optional[AnalysisResult]:
    """Analyzes text using the Analyst Agent."""
    system_prompt = """
    You are an expert Confluence Documentation Analyst Agent.
    Your task is to analyze the raw text extracted from Confluence and identify flaws,
    outdated information, missing formatting, or inconsistencies.

    Provide your response as a JSON object matching this schema:
    {
      "critiques": [
        {
          "finding": "Specific description of the issue.",
          "severity": "low, medium, or high",
          "recommendation": "How to fix the issue."
        }
      ],
      "overall_quality": "Overall assessment of the text quality."
    }
    """

    prompt = f"Analyze the following Confluence page content:\n\n{text}"

    response_text = await generate_response(prompt, system_prompt)

    if not response_text:
        return None

    try:
        cleaned_json = clean_json_response(response_text)
        data = json.loads(cleaned_json)

        # Normalize severity to lowercase as required by the model
        for critique in data.get("critiques", []):
            if "severity" in critique:
                critique["severity"] = str(critique["severity"]).lower()

        return AnalysisResult(**data)
    except json.JSONDecodeError:
        return None
    except Exception:
        return None
