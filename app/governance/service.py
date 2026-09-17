from uuid import uuid4

from app.agent.governance_workflow import run_governance_agent
from app.core.config import settings
from app.governance.models import (
    AnalyzeResponse,
    CustomerQuestion,
    EditDraftRequest,
    KnowledgeDraft,
    ReviewAction,
    ReviewStatus,
    UnansweredQuestion,
)
from app.governance.store import governance_store
from app.rag.document_loader import split_text_to_documents
from app.rag.vector_store import add_documents

UNCOVERED_ANSWER_MARKERS = [
    "知识库暂无",
    "知识库中暂未",
    "暂未找到",
    "未找到相关",
    "没有相关信息",
    "没有足够信息",
    "无法从知识库",
    "not found in the knowledge base",
    "no relevant information",
]


def normalize_questions(items: list[str | CustomerQuestion]) -> list[CustomerQuestion]:
    questions = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, CustomerQuestion):
            questions.append(item)
            continue
        text = str(item).strip()
        if text:
            questions.append(CustomerQuestion(id=f"q_{index}_{uuid4().hex[:6]}", text=text))
    return questions


def analyze_questions(items: list[str | CustomerQuestion], top_k: int = 4) -> AnalyzeResponse:
    questions = normalize_questions(items)
    result = run_governance_agent(questions, top_k=top_k)
    state = governance_store.replace_analysis(result["gaps"], result["clusters"], result["drafts"])
    return AnalyzeResponse(gaps=state.gaps, clusters=state.clusters, drafts=state.drafts)


def list_gaps():
    return governance_store.load().gaps


def list_drafts():
    return governance_store.load().drafts


def list_unanswered_questions(status: str = "pending"):
    questions = governance_store.load().unanswered_questions
    if status == "all":
        return questions
    return [item for item in questions if item.status == status]


def _top_score(sources: list[dict]) -> float | None:
    if not sources:
        return None
    score = sources[0].get("score")
    if score is None:
        return None
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def should_record_unanswered(answer: str, sources: list[dict]) -> bool:
    top_score = _top_score(sources)
    answer_lower = answer.lower()
    if not sources:
        return True
    if top_score is None:
        return True
    if top_score < settings.governance_min_source_score:
        return True
    return any(marker.lower() in answer_lower for marker in UNCOVERED_ANSWER_MARKERS)


def record_unanswered_from_rag(result: dict) -> UnansweredQuestion | None:
    answer = str(result.get("answer") or result.get("reply") or "")
    sources = list(result.get("sources") or [])
    if not should_record_unanswered(answer, sources):
        return None

    item = UnansweredQuestion(
        id=f"unanswered_{uuid4().hex[:10]}",
        question=str(result.get("question") or ""),
        session_id=result.get("session_id"),
        top_sources=sources[:5],
        top_score=_top_score(sources),
        answer=answer,
        status="pending",
    )
    governance_store.add_unanswered_question(item)
    return item


def draft_to_markdown(draft: KnowledgeDraft) -> str:
    evidence = "\n".join(f"- {item}" for item in draft.required_evidence)
    risks = "\n".join(f"- {item}" for item in draft.risk_notes)
    questions = "\n".join(f"- {item}" for item in draft.source_questions)
    return (
        f"# {draft.title}\n\n"
        f"## 主题\n{draft.topic}\n\n"
        f"## 适用问题\n{questions}\n\n"
        f"## 标准回答\n{draft.standard_answer}\n\n"
        f"## 需要确认的信息\n{evidence}\n\n"
        f"## 风险提示\n{risks}\n\n"
        f"## 来源\n客服知识库治理 Agent，草稿 ID：{draft.id}\n"
    )


def approve_draft(draft_id: str) -> KnowledgeDraft:
    draft = governance_store.get_draft(draft_id)
    if draft is None:
        raise KeyError(f"Draft not found: {draft_id}")
    if draft.review_status == ReviewStatus.approved:
        return draft

    source_file = f"governance_draft_{draft.id}.md"
    metadata = {
        "source": "governance_draft",
        "draft_id": draft.id,
        "topic": draft.topic,
        "review_status": ReviewStatus.approved.value,
    }
    chunks = split_text_to_documents(draft_to_markdown(draft), source_file, metadata)
    draft.published_chunks = add_documents(chunks)
    draft.review_status = ReviewStatus.approved
    draft.rejection_reason = None
    governance_store.update_draft(draft, ReviewAction.approve)
    return draft


def reject_draft(draft_id: str, reason: str) -> KnowledgeDraft:
    return governance_store.mark_rejected(draft_id, reason)


def edit_draft(draft_id: str, req: EditDraftRequest) -> KnowledgeDraft:
    draft = governance_store.get_draft(draft_id)
    if draft is None:
        raise KeyError(f"Draft not found: {draft_id}")
    if draft.review_status == ReviewStatus.approved:
        raise ValueError("Published drafts cannot be edited. Create a new draft for revised knowledge.")

    if req.title is not None:
        draft.title = req.title
    if req.standard_answer is not None:
        draft.standard_answer = req.standard_answer
    if req.required_evidence is not None:
        draft.required_evidence = req.required_evidence
    if req.risk_notes is not None:
        draft.risk_notes = req.risk_notes
    if req.confidence is not None:
        draft.confidence = req.confidence
    draft.review_status = ReviewStatus.pending
    draft.rejection_reason = None
    governance_store.update_draft(draft, ReviewAction.edit)
    return draft
