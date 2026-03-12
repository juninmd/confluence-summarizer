from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class RefinementStatus(str, Enum):
    """Status of a refinement job."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_REVISION = "NEEDS_REVISION"
    REJECTED = "REJECTED"


class Critique(BaseModel):
    """A critique identified by the Analyst Agent."""
    finding: str = Field(..., description="The issue found in the text.")
    severity: str = Field(..., description="The severity of the issue (e.g., low, medium, high).")
    recommendation: str = Field(..., description="How to fix the issue.")


class AnalysisResult(BaseModel):
    """The complete analysis from the Analyst Agent."""
    critiques: List[Critique] = Field(default_factory=list, description="List of issues found.")  # type: ignore
    overall_quality: str = Field(..., description="Overall assessment of the text quality.")


class ReviewResult(BaseModel):
    """The review result from the Reviewer Agent."""
    status: RefinementStatus = Field(..., description="The final status of the review.")
    comments: str = Field(..., description="Comments explaining the review decision.")


class RefinementJob(BaseModel):
    """Represents a job to refine a Confluence page."""
    page_id: str
    space_key: str
    status: RefinementStatus = RefinementStatus.PENDING
    original_content: Optional[str] = None
    refined_content: Optional[str] = None
    analysis: Optional[AnalysisResult] = None
    review: Optional[ReviewResult] = None
    error_message: Optional[str] = None
