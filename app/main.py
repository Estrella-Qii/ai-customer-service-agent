from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.llm import chat
from app.memory.store import get_conversation_memory
from routers.documents import router as documents_router
from routers.rag import router as rag_router
from routers.sessions import router as sessions_router

app = FastAPI(
    title="AI 智能客服 Agent",
    description="基于 FastAPI、DeepSeek、Embedding、Redis 和 Qdrant 的 RAG 智能客服后端。",
    version="0.3.0",
)
app.include_router(documents_router)
app.include_router(rag_router)
app.include_router(sessions_router)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户消息")
    session_id: str | None = Field(None, description="会话 ID；不传则自动生成")


@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    session_id = req.session_id or str(uuid4())
    memory = get_conversation_memory()
    history = memory.get_messages(session_id)

    messages = [
        {"role": "system", "content": "你是一个专业、耐心、简洁的智能客服助手。"},
        *history,
        {"role": "user", "content": req.message},
    ]
    reply = chat(messages)

    memory.append_message(session_id, "user", req.message)
    memory.append_message(session_id, "assistant", reply)

    return {
        "session_id": session_id,
        "reply": reply,
        "memory_backend": memory.backend(),
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}
