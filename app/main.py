from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.llm import chat
from routers.documents import router as documents_router
from routers.rag import router as rag_router

app = FastAPI(
    title="AI 智能客服 Agent",
    description="基于 FastAPI、DeepSeek、Embedding 和 Qdrant 的 RAG 智能客服后端。",
    version="0.1.0",
)
app.include_router(documents_router)
app.include_router(rag_router)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户消息")


@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    messages = [
        {"role": "system", "content": "你是一个智能客服助手。"},
        {"role": "user", "content": req.message},
    ]
    reply = chat(messages)
    return {"reply": reply}


@app.get("/health")
def health_check():
    return {"status": "ok"}
