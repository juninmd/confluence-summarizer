"""LLM steps of curation: compare sources, unify them, review the result."""

import json
import logging
from typing import List

from pydantic import ValidationError

from src.agents.common import clean_json_response, generate_response
from src.agents.reviewer import ReviewResult, parse_review
from src.curation import prompts
from src.curation.models import Comparison, Conflict, SourcePage

logger = logging.getLogger(__name__)

_MAX_CHARS = 12000  # per source page, keeps prompts inside the model context


def render_sources(pages: List[SourcePage]) -> str:
    """Serialize source pages for a prompt, including the freshness evidence."""
    return "\n\n".join(
        f"=== PAGE id={p.id} title={p.title!r} version={p.version} updated_at={p.updated_at}\n"
        f"{p.markdown[:_MAX_CHARS]}"
        for p in pages
    )


async def compare(pages: List[SourcePage]) -> Comparison:
    """Detect contradictions/outdated content; unparseable output asks for human review."""
    raw = await generate_response(
        prompt=render_sources(pages),
        system_prompt=prompts.COMPARE_SYSTEM,
        temperature=0.1,
    )
    try:
        return Comparison(**json.loads(clean_json_response(raw)))
    except (json.JSONDecodeError, ValidationError, TypeError):
        logger.warning("Comparison output unparseable; flagging for human review")
        failed = Conflict(
            topic="Automatic comparison failed",
            resolution=f"Compare pages {[p.id for p in pages]} manually",
            needs_human=True,
        )
        return Comparison(conflicts=[failed])


async def unify(pages: List[SourcePage], comparison: Comparison) -> str:
    """Write the canonical document from the sources and the analyst's resolutions."""
    prompt = (
        f"Sources:\n{render_sources(pages)}\n\n"
        f"Analyst findings (JSON):\n{comparison.model_dump_json()}"
    )
    doc = await generate_response(
        prompt=prompt, system_prompt=prompts.UNIFY_SYSTEM, temperature=0.2
    )
    if not doc.strip():
        raise ValueError("Writer returned an empty document")
    return doc.strip() + "\n"


async def review(pages: List[SourcePage], doc: str) -> ReviewResult:
    prompt = f"Sources:\n{render_sources(pages)}\n\nUnified document:\n{doc}"
    raw = await generate_response(
        prompt=prompt, system_prompt=prompts.REVIEW_SYSTEM, temperature=0.0
    )
    return parse_review(raw)
