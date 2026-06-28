from app.agent.workflow import run_customer_service_agent


def answer_with_rag(question: str, top_k: int = 4, session_id: str | None = None) -> dict:
    return run_customer_service_agent(question=question, top_k=top_k, session_id=session_id)
