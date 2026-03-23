import enum
from typing import Optional
from pydantic import BaseModel, Field


class RefinementStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class Critique(BaseModel):
    issue: str = Field(..., description="The problem identified in the text")
    severity: str = Field(..., description="Severity of the issue (high, medium, low)")
    suggestion: str = Field(..., description="Suggestion on how to fix the issue")


class PageData(BaseModel):
    page_id: str
    space_key: str
    title: str
    content: str
    version: int


class JobStatus(BaseModel):
    job_id: str
    status: RefinementStatus
    page_id: Optional[str] = None
    space_key: Optional[str] = None
    error: Optional[str] = None
    created_at: float
    updated_at: float
