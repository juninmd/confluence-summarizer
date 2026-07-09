import logging
from typing import List

from src.confluence_summarizer.agents import analyst, reviewer, writer
from src.confluence_summarizer.models.domain import AnalysisResult, RefinementStatus
from src.confluence_summarizer.agents.reviewer import ReviewResult

logger = logging.getLogger(__name__)


async def execute_refinement_pipeline(
    original_text: str, context: List[str]
) -> tuple[RefinementStatus, str, str]:
    """Execute the AI agent orchestration pipeline (Analyst -> Writer -> Reviewer).

    Args:
        original_text: The original Confluence documentation text.
        context: Context text retrieved from the vector database.

    Returns:
        A tuple of (RefinementStatus, refined_text, error_message)
    """
    try:
        # Step 1: Analyst Agent
        logger.info("Orchestrator: Calling Analyst Agent")
        analysis: AnalysisResult = await analyst.analyze_content(original_text, context)

        if not analysis.critiques:
            logger.info("Orchestrator: No critiques found. Marking as completed.")
            return RefinementStatus.COMPLETED, original_text, ""

        # Step 2: Writer Agent
        logger.info("Orchestrator: Calling Writer Agent")
        rewritten_text: str = await writer.rewrite_content(
            original_text, analysis, context
        )

        # Step 3: Reviewer Agent
        logger.info("Orchestrator: Calling Reviewer Agent")
        review: ReviewResult = await reviewer.review_content(
            original_text, rewritten_text, analysis
        )

        if review.status == RefinementStatus.COMPLETED:
            return RefinementStatus.COMPLETED, rewritten_text, ""
        else:
            return (
                RefinementStatus.FAILED,
                original_text,
                f"Reviewer rejected changes. Reason: {review.feedback}",
            )
    except Exception as e:
        logger.exception("Orchestrator: Pipeline execution failed.")
        return RefinementStatus.FAILED, original_text, str(e)
