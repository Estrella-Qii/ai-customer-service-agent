import json
import re
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.governance.models import (
    CoverageResult,
    CustomerQuestion,
    GapCluster,
    KnowledgeDraft,
    KnowledgeGap,
    RetrievedContext,
)
from app.llm import chat
from app.rag.retriever import retrieve


class GovernanceState(TypedDict):
    questions: list[CustomerQuestion]
    top_k: int
    coverage_results: list[CoverageResult]
    gaps: list[KnowledgeGap]
    clusters: list[GapCluster]
    drafts: list[KnowledgeDraft]


def _safe_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def _keyword_topic(question: str) -> str:
    rules = [
        ("优惠券规则", ["优惠券", "券", "补发", "过期"]),
        ("发票规则", ["发票", "抬头", "税号"]),
        ("订单改地址", ["改地址", "地址", "收货信息"]),
        ("企业采购", ["企业", "对公", "采购", "转账"]),
        ("会员积分", ["积分", "会员"]),
        ("退款时效", ["退款", "到账"]),
        ("物流异常", ["物流", "快递", "签收", "丢件"]),
        ("换货规则", ["换货", "尺码", "颜色"]),
    ]
    for topic, keywords in rules:
        if any(keyword in question for keyword in keywords):
            return topic
    return "其他高频问题"


def _context_overlap(question: str, contexts: list[RetrievedContext]) -> float:
    tokens = {char for char in question if "\u4e00" <= char <= "\u9fff"}
    if not tokens:
        return 0
    content = "".join(context.content for context in contexts[:3])
    matched = sum(1 for token in tokens if token in content)
    return matched / max(len(tokens), 1)


def _heuristic_coverage(question: CustomerQuestion, contexts: list[RetrievedContext]) -> CoverageResult:
    if not contexts:
        return CoverageResult(
            question=question,
            status="gap",
            reason="现有知识库没有检索到相关片段。",
            suggested_topic=_keyword_topic(question.text),
            confidence=0.78,
            contexts=[],
        )

    overlap = _context_overlap(question.text, contexts)
    best_score = contexts[0].score if contexts[0].score is not None else None
    if overlap < 0.18:
        status = "gap"
        reason = "检索结果与用户问题的关键词重合较少，疑似知识库缺口。"
        confidence = 0.7
    elif overlap < 0.3 or (best_score is not None and best_score < settings.governance_min_source_score):
        status = "weakly_covered"
        reason = "检索到部分相关内容，但不足以稳定支撑标准客服回答。"
        confidence = 0.64
    else:
        status = "covered"
        reason = "检索结果与问题较相关，初步判断可由现有知识库覆盖。"
        confidence = 0.68

    return CoverageResult(
        question=question,
        status=status,
        reason=reason,
        suggested_topic=_keyword_topic(question.text),
        confidence=confidence,
        contexts=contexts,
    )


def _llm_coverage(question: CustomerQuestion, contexts: list[RetrievedContext]) -> CoverageResult:
    heuristic = _heuristic_coverage(question, contexts)
    if heuristic.status in {"gap", "covered"}:
        return heuristic

    context_text = "\n\n".join(
        f"[{index}] source={item.source}, score={item.score}\n{item.content}"
        for index, item in enumerate(contexts[:4], start=1)
    )
    messages = [
        {
            "role": "system",
            "content": (
                "你是客服知识库治理专员。判断现有知识库片段是否足够回答用户问题。"
                "只输出 JSON，字段为 status、reason、suggested_topic、confidence。"
                "status 只能是 covered、weakly_covered、gap。confidence 是 0 到 1 的数字。"
            ),
        },
        {
            "role": "user",
            "content": f"用户问题：{question.text}\n\n知识库片段：\n{context_text}",
        },
    ]
    try:
        data = _safe_json(chat(messages))
    except Exception:
        return heuristic

    status = data.get("status")
    if status not in {"covered", "weakly_covered", "gap"}:
        status = heuristic.status
    confidence = data.get("confidence", heuristic.confidence)
    try:
        confidence = max(0, min(1, float(confidence)))
    except (TypeError, ValueError):
        confidence = heuristic.confidence

    return CoverageResult(
        question=question,
        status=status,
        reason=str(data.get("reason") or heuristic.reason),
        suggested_topic=str(data.get("suggested_topic") or heuristic.suggested_topic or _keyword_topic(question.text)),
        confidence=confidence,
        contexts=contexts,
    )


def _retrieve_knowledge(state: GovernanceState) -> GovernanceState:
    results: list[CoverageResult] = []
    for question in state["questions"]:
        raw_contexts = retrieve(question.text, state["top_k"])
        contexts = [RetrievedContext(**item) for item in raw_contexts]
        results.append(_llm_coverage(question, contexts))
    return {**state, "coverage_results": results}


def _extract_gaps(state: GovernanceState) -> GovernanceState:
    gaps = []
    for result in state["coverage_results"]:
        if result.status == "covered":
            continue
        gaps.append(
            KnowledgeGap(
                id=f"gap_{uuid4().hex[:10]}",
                question_id=result.question.id,
                question=result.question.text,
                reason=result.reason,
                suggested_topic=result.suggested_topic or _keyword_topic(result.question.text),
                coverage_status=result.status,
                confidence=result.confidence,
            )
        )
    return {**state, "gaps": gaps}


def _cluster_gaps(state: GovernanceState) -> GovernanceState:
    groups: dict[str, list[KnowledgeGap]] = {}
    for gap in state["gaps"]:
        topic = gap.suggested_topic.strip() or _keyword_topic(gap.question)
        groups.setdefault(topic, []).append(gap)

    clusters = []
    for topic, gaps in groups.items():
        avg_confidence = sum(gap.confidence for gap in gaps) / len(gaps)
        clusters.append(
            GapCluster(
                id=f"cluster_{uuid4().hex[:10]}",
                topic=topic,
                gap_ids=[gap.id for gap in gaps],
                questions=[gap.question for gap in gaps],
                frequency=len(gaps),
                summary=f"{len(gaps)} 个历史问题显示“{topic}”存在知识库覆盖不足。",
                confidence=round(avg_confidence, 2),
            )
        )
    clusters.sort(key=lambda item: item.frequency, reverse=True)
    return {**state, "clusters": clusters}


def _fallback_draft(cluster: GapCluster) -> KnowledgeDraft:
    title = f"{cluster.topic}处理规则"
    answer = (
        f"当用户咨询{cluster.topic}相关问题时，客服应先确认订单、账号或活动信息，"
        "再根据平台当前政策进行处理。若系统无法自动判断，应升级给人工客服或相关业务团队核实，"
        "避免承诺未确认的补偿、退款或时效。"
    )
    return KnowledgeDraft(
        id=f"draft_{uuid4().hex[:10]}",
        title=title,
        topic=cluster.topic,
        problem_cluster=cluster.id,
        standard_answer=answer,
        required_evidence=["用户账号或订单号", "问题发生时间", "相关活动或商品信息"],
        risk_notes=["不要承诺知识库未明确支持的补偿方案。", "涉及金额、发票、对公转账时需按业务规则复核。"],
        source_questions=cluster.questions,
        confidence=cluster.confidence,
    )


def _llm_draft(cluster: GapCluster) -> KnowledgeDraft:
    fallback = _fallback_draft(cluster)
    messages = [
        {
            "role": "system",
            "content": (
                "你是企业客服知识库运营专家。请基于同类历史问题生成一篇知识库文章草稿。"
                "不要写成聊天回复，要写成客服内部可复用的标准知识文章。"
                "只输出 JSON，字段为 title、standard_answer、required_evidence、risk_notes、confidence。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"主题：{cluster.topic}\n"
                f"历史问题：{json.dumps(cluster.questions, ensure_ascii=False)}\n"
                "请覆盖：适用问题、标准回答、需要用户/系统确认的信息、风险提示。"
            ),
        },
    ]
    try:
        data = _safe_json(chat(messages))
    except Exception:
        return fallback

    required_evidence = data.get("required_evidence") or fallback.required_evidence
    risk_notes = data.get("risk_notes") or fallback.risk_notes
    if not isinstance(required_evidence, list):
        required_evidence = fallback.required_evidence
    if not isinstance(risk_notes, list):
        risk_notes = fallback.risk_notes

    try:
        confidence = max(0, min(1, float(data.get("confidence", fallback.confidence))))
    except (TypeError, ValueError):
        confidence = fallback.confidence

    return KnowledgeDraft(
        id=fallback.id,
        title=str(data.get("title") or fallback.title),
        topic=cluster.topic,
        problem_cluster=cluster.id,
        standard_answer=str(data.get("standard_answer") or fallback.standard_answer),
        required_evidence=[str(item) for item in required_evidence],
        risk_notes=[str(item) for item in risk_notes],
        source_questions=cluster.questions,
        confidence=round(confidence, 2),
    )


def _generate_drafts(state: GovernanceState) -> GovernanceState:
    drafts = [
        _llm_draft(cluster) if cluster.frequency >= 2 else _fallback_draft(cluster) for cluster in state["clusters"]
    ]
    return {**state, "drafts": drafts}


def build_governance_graph():
    graph = StateGraph(GovernanceState)
    graph.add_node("retrieve_knowledge", _retrieve_knowledge)
    graph.add_node("extract_gaps", _extract_gaps)
    graph.add_node("cluster_gaps", _cluster_gaps)
    graph.add_node("generate_drafts", _generate_drafts)

    graph.set_entry_point("retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "extract_gaps")
    graph.add_edge("extract_gaps", "cluster_gaps")
    graph.add_edge("cluster_gaps", "generate_drafts")
    graph.add_edge("generate_drafts", END)
    return graph.compile()


governance_graph = build_governance_graph()


def run_governance_agent(questions: list[CustomerQuestion], top_k: int = 4) -> dict:
    return governance_graph.invoke(
        {
            "questions": questions,
            "top_k": top_k,
            "coverage_results": [],
            "gaps": [],
            "clusters": [],
            "drafts": [],
        }
    )
