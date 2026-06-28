from openai import OpenAI

from app.core.config import settings

client = OpenAI(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
)

def chat(messages: list[dict]) -> str:
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
    )
    return response.choices[0].message.content
