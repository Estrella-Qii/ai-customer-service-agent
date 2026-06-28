from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.rag.qa import answer_with_rag

router = APIRouter(prefix="/rag", tags=["RAG问答"])


class RagAskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")
    top_k: int = Field(4, ge=1, le=20, description="检索多少个相关文档片段")


@router.post("/ask")
async def ask_with_rag(req: RagAskRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, detail="问题不能为空")

    try:
        return answer_with_rag(question, req.top_k)
    except Exception as exc:
        raise HTTPException(500, detail=f"RAG 问答失败: {exc}") from exc
