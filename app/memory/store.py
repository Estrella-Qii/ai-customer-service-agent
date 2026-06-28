import json
from functools import lru_cache
from typing import Any

from app.core.config import settings

_fallback_store: dict[str, list[dict[str, str]]] = {}


class ConversationMemory:
    def __init__(self) -> None:
        self._redis = self._build_redis_client()

    def _build_redis_client(self) -> Any | None:
        try:
            import redis

            client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            client.ping()
            return client
        except Exception:
            return None

    def _key(self, session_id: str) -> str:
        return f"conversation:{session_id}"

    def get_messages(self, session_id: str) -> list[dict[str, str]]:
        if self._redis is None:
            return list(_fallback_store.get(session_id, []))

        raw_items = self._redis.lrange(self._key(session_id), 0, -1)
        messages: list[dict[str, str]] = []
        for item in raw_items:
            try:
                data = json.loads(item)
            except json.JSONDecodeError:
                continue
            if data.get("role") in {"user", "assistant"} and data.get("content"):
                messages.append({"role": data["role"], "content": data["content"]})
        return messages

    def append_message(self, session_id: str, role: str, content: str) -> None:
        if role not in {"user", "assistant"} or not content:
            return

        message = {"role": role, "content": content}
        if self._redis is None:
            history = _fallback_store.setdefault(session_id, [])
            history.append(message)
            del history[:-settings.max_history_messages]
            return

        key = self._key(session_id)
        self._redis.rpush(key, json.dumps(message, ensure_ascii=False))
        self._redis.ltrim(key, -settings.max_history_messages, -1)
        self._redis.expire(key, settings.conversation_ttl_seconds)

    def clear(self, session_id: str) -> None:
        if self._redis is None:
            _fallback_store.pop(session_id, None)
            return

        self._redis.delete(self._key(session_id))

    def backend(self) -> str:
        return "redis" if self._redis is not None else "memory"


@lru_cache
def get_conversation_memory() -> ConversationMemory:
    return ConversationMemory()
