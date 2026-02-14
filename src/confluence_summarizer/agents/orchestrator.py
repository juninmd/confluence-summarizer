from ..models import RefinementResult, RefinementStatus, ConfluencePage
from ..services import rag
from . import analyst, writer, reviewer


async def refine_page(page: ConfluencePage) -> RefinementResult:
    """
    Orchestrates the refinement process for a single page.
    """
    # 1. Retrieve Context (similar pages that might contradict or support)
    # We query BEFORE ingesting the current page to avoid retrieving the page itself as context
    # (assuming we want to check against existing knowledge).
    context_docs = await rag.query_context(page.body, exclude_page_id=page.id)

    # 2. Ingest into RAG (update knowledge base with current version)
    await rag.ingest_page(page)

    # 3. Analyst Agent
    critiques = await analyst.analyze_content(page.body, context_docs)

    if not critiques:
        return RefinementResult(
            page_id=page.id,
            original_content=page.body,
            status=RefinementStatus.COMPLETED,
            reviewer_comments="No critiques found."
        )

    # 4. Writer Agent
    # Pass context_docs so the writer can ensure consistency
    new_content = await writer.rewrite_content(page.body, critiques, context_docs)

    # 5. Reviewer Agent
    critiques_summary = "\n".join([c.description for c in critiques])
    review = await reviewer.review_content(page.body, new_content, critiques_summary)

    return RefinementResult(
        page_id=page.id,
        original_content=page.body,
        critiques=critiques,
        rewritten_content=new_content,
        status=review["status"],
        reviewer_comments=review["comments"]
    )
