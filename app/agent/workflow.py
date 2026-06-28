from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.llm import chat
from app.memory.store import get_conversation_memory
from app.rag.retriever import retrieve


class CustomerServiceState(TypedDict):
    question: str
    top_k: int
    session_id: str
    history: list[dict[str, str]]
    contexts: list[dict]
    context_text: str
    answer: str
    memory_backend: str


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


def _load_memory(state: CustomerServiceState) -> CustomerServiceState:
    memory = get_conversation_memory()
    return {
        **state,
        "history": memory.get_messages(state["session_id"]),
        "memory_backend": memory.backend(),
    }


def _retrieve_context(state: CustomerServiceState) -> CustomerServiceState:
    contexts = retrieve(state["question"], state["top_k"])
    return {
        **state,
        "contexts": contexts,
        "context_text": _format_context(contexts),
    }


def _generate_answer(state: CustomerServiceState) -> CustomerServiceState:
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
        *state["history"],
        {
            "role": "user",
            "content": (
                f"用户问题：{state['question']}\n\n"
                f"知识库资料：\n{state['context_text']}\n\n"
                "请给出客服回复，并在最后用一句话说明参考了哪些文件。"
            ),
        },
    ]
    return {**state, "answer": chat(messages)}


def _save_memory(state: CustomerServiceState) -> CustomerServiceState:
    memory = get_conversation_memory()
    memory.append_message(state["session_id"], "user", state["question"])
    memory.append_message(state["session_id"], "assistant", state["answer"])
    return {**state, "memory_backend": memory.backend()}


def build_customer_service_graph():
    graph = StateGraph(CustomerServiceState)
    graph.add_node("load_memory", _load_memory)
    graph.add_node("retrieve_context", _retrieve_context)
    graph.add_node("generate_answer", _generate_answer)
    graph.add_node("save_memory", _save_memory)

    graph.set_entry_point("load_memory")
    graph.add_edge("load_memory", "retrieve_context")
    graph.add_edge("retrieve_context", "generate_answer")
    graph.add_edge("generate_answer", "save_memory")
    graph.add_edge("save_memory", END)
    return graph.compile()


customer_service_graph = build_customer_service_graph()


def run_customer_service_agent(question: str, top_k: int = 4, session_id: str | None = None) -> dict:
    session_id = session_id or str(uuid4())
    result = customer_service_graph.invoke(
        {
            "question": question,
            "top_k": top_k,
            "session_id": session_id,
            "history": [],
            "contexts": [],
            "context_text": "",
            "answer": "",
            "memory_backend": "",
        }
    )

    return {
        "session_id": result["session_id"],
        "question": result["question"],
        "answer": result["answer"],
        "memory_backend": result["memory_backend"],
        "workflow": ["load_memory", "retrieve_context", "generate_answer", "save_memory"],
        "sources": [
            {
                "source": item.get("source", "unknown"),
                "chunk_index": item.get("chunk_index"),
                "score": item.get("score"),
            }
            for item in result["contexts"]
        ],
        "contexts": result["contexts"],
    }
