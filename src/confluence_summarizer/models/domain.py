from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class RefinementStatus(str, Enum):
    """Status de um job de refinamento."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class CritiqueSeverity(str, Enum):
    """Níveis de severidade das críticas."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Critique(BaseModel):
    """Modelo representando uma crítica individual na avaliação do Analyst Agent."""
    issue: str = Field(description="A descrição da falha, desatualização ou problema de formatação encontrado.")
    severity: CritiqueSeverity = Field(description="Severidade: low, medium, high, ou critical.")
    suggestion: str = Field(description="Sugestão de como consertar ou melhorar o problema.")


class AnalystResponse(BaseModel):
    """Resposta estruturada do Analyst Agent."""
    critiques: List[Critique]


class ReviewerResponse(BaseModel):
    """Resposta do Reviewer Agent avaliando o trabalho do Writer."""
    status: str = Field(description="O status final da revisão (ex: 'approved', 'rejected').")
    feedback: str = Field(description="Feedback descrevendo o motivo da aprovação ou rejeição.")


class JobRecord(BaseModel):
    """Registro de um job salvo no banco de dados SQLite."""
    job_id: str
    page_id: str
    status: str
    result: str | None = None
    error: str | None = None
