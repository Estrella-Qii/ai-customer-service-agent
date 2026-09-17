from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import settings

CoverageStatus = Literal["covered", "weakly_covered", "gap"]


class ReviewStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ReviewAction(StrEnum):
    approve = "approve"
    reject = "reject"
    edit = "edit"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class CustomerQuestion(BaseModel):
    id: str
    text: str = Field(..., min_length=1, max_length=settings.max_question_chars)
    channel: str | None = None
    asked_at: str | None = None


class RetrievedContext(BaseModel):
    content: str
    source: str = "unknown"
    chunk_index: int | None = None
    score: float | None = None


class CoverageResult(BaseModel):
    question: CustomerQuestion
    status: CoverageStatus
    reason: str
    suggested_topic: str
    confidence: float = Field(ge=0, le=1)
    contexts: list[RetrievedContext] = Field(default_factory=list)


class KnowledgeGap(BaseModel):
    id: str
    question_id: str
    question: str
    reason: str
    suggested_topic: str
    coverage_status: CoverageStatus
    confidence: float = Field(ge=0, le=1)
    created_at: str = Field(default_factory=utc_now)


class GapCluster(BaseModel):
    id: str
    topic: str
    gap_ids: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    frequency: int = 0
    summary: str = ""
    confidence: float = Field(ge=0, le=1, default=0.5)


class KnowledgeDraft(BaseModel):
    id: str
    title: str
    topic: str
    problem_cluster: str
    standard_answer: str
    required_evidence: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    source_questions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus = ReviewStatus.pending
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    published_chunks: int = 0
    rejection_reason: str | None = None


class UnansweredQuestion(BaseModel):
    id: str
    question: str
    session_id: str | None = None
    timestamp: str = Field(default_factory=utc_now)
    top_sources: list[dict] = Field(default_factory=list)
    top_score: float | None = None
    answer: str = ""
    status: str = "pending"


class ReviewRecord(BaseModel):
    draft_id: str
    action: ReviewAction
    reason: str | None = None
    created_at: str = Field(default_factory=utc_now)


class GovernanceState(BaseModel):
    gaps: list[KnowledgeGap] = Field(default_factory=list)
    clusters: list[GapCluster] = Field(default_factory=list)
    drafts: list[KnowledgeDraft] = Field(default_factory=list)
    review_history: list[ReviewRecord] = Field(default_factory=list)
    unanswered_questions: list[UnansweredQuestion] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    questions: list[str | CustomerQuestion] = Field(..., min_length=1, max_length=100)
    top_k: int = Field(4, ge=1, le=20)


class AnalyzeResponse(BaseModel):
    gaps: list[KnowledgeGap]
    clusters: list[GapCluster]
    drafts: list[KnowledgeDraft]


class RejectDraftRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class EditDraftRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    standard_answer: str | None = Field(None, min_length=1, max_length=10000)
    required_evidence: list[str] | None = None
    risk_notes: list[str] | None = None
    confidence: float | None = Field(None, ge=0, le=1)
