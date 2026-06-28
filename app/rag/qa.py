from uuid import uuid4

from app.llm import chat
from app.memory.store import get_conversation_memory
from app.rag.retriever import retrieve


def _format_context(results: list[dict]) -> str:
    if not results:
        return "未检索到相关知识库内容。"

    blocks = []
    for index, item in enumerate(results, start=1):
        source = item.get("source", "unknown")
        chunk_index = item.get("chunk_index")
        content = item.get("content", "")
        blocks.append(f"[资料{index}] 来源: {source}, 片段: {chunk_index}\n{content}")
    return "\n\n".join(blocks)


def answer_with_rag(question: str, top_k: int = 4, session_id: str | None = None) -> dict:
    session_id = session_id or str(uuid4())
    memory = get_conversation_memory()
    history = memory.get_messages(session_id)

    results = retrieve(question, top_k)
    context = _format_context(results)

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个专业、耐心的智能客服助手。"
                "请优先依据给定的知识库资料回答用户问题。"
                "如果资料中没有足够信息，请明确说明知识库里暂未找到答案，"
                "不要编造政策、价格、承诺或售后规则。"
                "回答要简洁、清楚、适合客服场景。"
            ),
        },
        *history,
        {
            "role": "user",
            "content": (
                f"用户问题：{question}\n\n"
                f"知识库资料：\n{context}\n\n"
                "请给出客服回复，并在最后用一句话说明参考了哪些文件。"
            ),
        },
    ]

    answer = chat(messages)
    memory.append_message(session_id, "user", question)
    memory.append_message(session_id, "assistant", answer)

    return {
        "session_id": session_id,
        "question": question,
        "answer": answer,
        "memory_backend": memory.backend(),
        "sources": [
            {
                "source": item.get("source", "unknown"),
                "chunk_index": item.get("chunk_index"),
                "score": item.get("score"),
            }
            for item in results
        ],
        "contexts": results,
    }
