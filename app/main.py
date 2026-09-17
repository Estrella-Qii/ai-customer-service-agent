from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.__about__ import __version__
from app.core.config import settings
from app.llm import chat
from app.memory.store import get_conversation_memory
from app.rag.vector_store import get_qdrant_client
from routers.documents import router as documents_router
from routers.governance import router as governance_router
from routers.rag import router as rag_router
from routers.sessions import router as sessions_router

app = FastAPI(
    title="Self-hosted RAG Customer Service Agent",
    description="FastAPI、LangGraph、Qdrant 和 Redis 驱动的可自托管 RAG 客服 Agent。",
    version=__version__,
)
app.include_router(documents_router)
app.include_router(rag_router)
app.include_router(sessions_router)
app.include_router(governance_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=settings.max_question_chars, description="用户消息")
    session_id: str | None = Field(None, min_length=1, max_length=128, description="会话 ID；不传则自动生成")


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
    return {"status": "ok", "version": __version__}


def _readiness_payload() -> tuple[bool, dict]:
    qdrant_ready = False
    qdrant_client = get_qdrant_client()
    try:
        qdrant_client.get_collections()
        qdrant_ready = True
    except Exception:
        qdrant_ready = False
    finally:
        qdrant_client.close()

    memory_backend = get_conversation_memory().backend()
    checks = {
        "llm_configured": settings.llm_is_configured(),
        "embedding_configured": settings.embedding_is_configured(),
        "qdrant": qdrant_ready,
        "memory_backend": memory_backend,
    }
    ready = checks["llm_configured"] and checks["embedding_configured"] and checks["qdrant"]
    return ready, {"status": "ready" if ready else "not_ready", "checks": checks}


@app.get("/health/status", tags=["Health"])
def dependency_status():
    """Return dependency status for operators and the Web UI without failing the request."""
    _, payload = _readiness_payload()
    return payload


@app.get("/health/ready", tags=["Health"])
def readiness_check():
    """Return HTTP 503 until the dependencies required for RAG requests are ready."""
    ready, payload = _readiness_payload()
    return JSONResponse(payload, status_code=200 if ready else 503)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("app/static/index.html")
