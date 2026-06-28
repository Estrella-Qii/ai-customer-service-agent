from fastapi import APIRouter

from app.memory.store import get_conversation_memory

router = APIRouter(prefix="/sessions", tags=["会话记忆"])


@router.get("/{session_id}/history")
async def get_session_history(session_id: str):
    memory = get_conversation_memory()
    return {
        "session_id": session_id,
        "backend": memory.backend(),
        "messages": memory.get_messages(session_id),
    }


@router.delete("/{session_id}")
async def clear_session_history(session_id: str):
    memory = get_conversation_memory()
    memory.clear(session_id)
    return {"session_id": session_id, "message": "会话记忆已清空"}
