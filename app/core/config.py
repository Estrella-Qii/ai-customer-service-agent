import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V4-Flash")
    siliconflow_api_key: str = os.getenv("SILICONFLOW_API_KEY", "")
    siliconflow_base_url: str = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-4B")
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "0"))
    qdrant_host: str = os.getenv("QDRANT_HOST", "127.0.0.1")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_url: str = os.getenv("QDRANT_URL") or f"http://{qdrant_host}:{qdrant_port}"
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "customer_service_docs")
    governance_min_source_score: float = float(os.getenv("GOVERNANCE_MIN_SOURCE_SCORE", "0.45"))
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "12"))
    conversation_ttl_seconds: int = int(os.getenv("CONVERSATION_TTL_SECONDS", "86400"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    max_question_chars: int = int(os.getenv("MAX_QUESTION_CHARS", "4000"))

    def require_llm(self) -> None:
        missing = []
        if not self.llm_api_key:
            missing.append("LLM_API_KEY")
        if not self.llm_base_url:
            missing.append("LLM_BASE_URL")
        if missing:
            raise RuntimeError(f"Missing LLM environment variables: {', '.join(missing)}")

    def require_embedding(self) -> None:
        missing = []
        if not self.siliconflow_api_key:
            missing.append("SILICONFLOW_API_KEY")
        if not self.siliconflow_base_url:
            missing.append("SILICONFLOW_BASE_URL")
        if not self.embedding_model:
            missing.append("EMBEDDING_MODEL")
        if missing:
            raise RuntimeError(f"Missing embedding environment variables: {', '.join(missing)}")

    def llm_is_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)

    def embedding_is_configured(self) -> bool:
        return bool(self.siliconflow_api_key and self.siliconflow_base_url and self.embedding_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
