from langchain_openai import OpenAIEmbeddings

from app.core.config import settings


def get_embeddings() -> OpenAIEmbeddings:
    settings.require_embedding()
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.siliconflow_api_key,
        base_url=settings.siliconflow_base_url,
        tiktoken_enabled=False,
        check_embedding_ctx_length=False,
    )
