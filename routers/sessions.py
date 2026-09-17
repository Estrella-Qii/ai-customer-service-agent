from typing import Annotated

from fastapi import APIRouter, Path

from app.memory.store import get_conversation_memory

router = APIRouter(prefix="/sessions", tags=["会话记忆"])
SessionId = Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]


@router.get("/{session_id}/history")
async def get_session_history(session_id: SessionId):
    memory = get_conversation_memory()
    return {
        "session_id": session_id,
        "backend": memory.backend(),
        "messages": memory.get_messages(session_id),
    }


@router.delete("/{session_id}")
async def clear_session_history(session_id: SessionId):
    memory = get_conversation_memory()
    memory.clear(session_id)
    return {"session_id": session_id, "message": "会话记忆已清空"}
