from functools import lru_cache

from openai import OpenAI

from app.core.config import settings


@lru_cache
def get_llm_client() -> OpenAI:
    settings.require_llm()
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def chat(messages: list[dict]) -> str:
    response = get_llm_client().chat.completions.create(
        model=settings.llm_model,
        messages=messages,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("The configured LLM returned an empty response.")
    return content
