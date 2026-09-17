import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.governance.service import record_unanswered_from_rag
from app.rag.qa import answer_with_rag

router = APIRouter(prefix="/rag", tags=["RAG"])
logger = logging.getLogger(__name__)


class RagAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=settings.max_question_chars, description="User question")
    top_k: int = Field(4, ge=1, le=20, description="Number of retrieved chunks")
    session_id: str | None = Field(None, min_length=1, max_length=128, description="Conversation session id")


@router.post("/ask")
async def ask_with_rag(req: RagAskRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, detail="Question cannot be empty")

    try:
        result = answer_with_rag(question, req.top_k, req.session_id)
        record_unanswered_from_rag(result)
        return result
    except Exception as exc:
        logger.exception("RAG request failed")
        raise HTTPException(503, detail="RAG request failed. Check model and vector-store availability.") from exc
