from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class RefinementStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfluencePage(BaseModel):
    id: str
    title: str
    space_key: str
    body: str
    version: int = 1
    url: str = ""


class CritiqueSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Critique(BaseModel):
    description: str = Field(
        description="Description of the issue found in the document."
    )
    severity: CritiqueSeverity = Field(
        description="Severity of the issue (low, medium, high)."
    )
    suggestion: str = Field(description="Suggestion on how to fix the issue.")


class AnalysisResult(BaseModel):
    critiques: List[Critique] = Field(
        description="A list of critiques for the analyzed text."
    )


class RefinementJob(BaseModel):
    id: str
    page_id: str
    status: RefinementStatus
    error: Optional[str] = None
    original_text: Optional[str] = None
    refined_text: Optional[str] = None
