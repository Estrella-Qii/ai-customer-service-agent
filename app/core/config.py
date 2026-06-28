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
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "customer_service_docs")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "12"))
    conversation_ttl_seconds: int = int(os.getenv("CONVERSATION_TTL_SECONDS", "86400"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
