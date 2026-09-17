import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_QUESTION = "\u4f18\u60e0\u5238\u8fc7\u671f\u4e86\u8fd8\u80fd\u8865\u53d1\u5417\uff1f"
AFTER_QUESTION = "\u4f18\u60e0\u5238\u8fc7\u671f\u540e\u8fd8\u80fd\u91cd\u65b0\u8865\u53d1\u5417\uff1f"
COUPON_KEYWORDS = ["\u4f18\u60e0\u5238", "\u6ee1\u51cf\u5238", "\u8865\u53d1", "\u8fc7\u671f", "\u6062\u590d"]


class DemoError(RuntimeError):
    pass


def request_json(
    base_url: str, method: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 120
) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DemoError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DemoError(f"Cannot connect to {base_url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise DemoError(
            f"{method} {path} timed out after {timeout}s. "
            "Governance analysis calls the LLM multiple times; retry with --timeout 300 or a smaller mock question set."
        ) from exc


def load_questions(path: Path) -> list[str]:
    if not path.exists():
        raise DemoError(f"Mock question file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    questions = data.get("questions", [])
    if not isinstance(questions, list) or not questions:
        raise DemoError(f"Mock question file has no questions: {path}")
    return [str(item) for item in questions if str(item).strip()]


def load_pending_questions(base_url: str, timeout: int) -> list[str]:
    payload = request_json(base_url, "GET", "/governance/unanswered_questions", timeout=timeout)
    questions = []
    for item in payload.get("questions", []) or []:
        question = str(item.get("question") or "").strip()
        if question:
            questions.append(question)
    return questions


def source_names(payload: dict[str, Any]) -> list[str]:
    names = []
    for item in payload.get("sources", []) or []:
        source = item.get("source")
        if source:
            names.append(str(source))
    return names


def has_governance_source(payload: dict[str, Any]) -> bool:
    return any("governance_draft" in source for source in source_names(payload))


def compact_answer(payload: dict[str, Any]) -> str:
    answer = payload.get("answer") or payload.get("reply") or ""
    return str(answer).strip()


def find_coupon_draft(drafts: list[dict[str, Any]]) -> dict[str, Any]:
    for draft in drafts:
        haystack = " ".join(
            [
                str(draft.get("title", "")),
                str(draft.get("topic", "")),
                " ".join(str(item) for item in draft.get("source_questions", []) or []),
            ]
        )
        if any(keyword in haystack for keyword in COUPON_KEYWORDS):
            return draft
    raise DemoError(
        "No coupon-related draft was generated. Check /governance/analyze output "
        "and make sure mock questions include coupon expiry questions."
    )


def print_section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def print_sources(label: str, sources: list[str]) -> None:
    print(f"{label}:")
    if not sources:
        print("  - <none>")
        return
    for source in sources:
        print(f"  - {source}")


def run_demo(args: argparse.Namespace) -> int:
    mock_path = Path(args.mock_file)

    print_section("1. Before governance: ask RAG")
    before = request_json(
        args.base_url,
        "POST",
        "/rag/ask",
        {
            "question": args.question,
            "top_k": args.top_k,
            "session_id": "governance-demo-before",
        },
        args.timeout,
    )
    before_sources = source_names(before)
    print(f"Question: {args.question}")
    print(f"Before answer:\n{compact_answer(before)}")
    print_sources("Before sources", before_sources)

    print_section("2. Governance analyze: find gaps and generate drafts")
    pending_questions = load_pending_questions(args.base_url, args.timeout)
    if args.questions_source == "pending":
        questions = pending_questions
        if not questions:
            raise DemoError(
                "No pending unanswered questions found. Ask an uncovered question through /rag/ask first, "
                "or rerun with --questions-source mock."
            )
        print(f"Using pending unanswered questions: {len(questions)}")
    elif args.questions_source == "mock":
        questions = load_questions(mock_path)
        print(f"Using mock customer questions: {len(questions)}")
    else:
        if pending_questions:
            questions = pending_questions
            print(f"Using pending unanswered questions: {len(questions)}")
        else:
            questions = load_questions(mock_path)
            print(f"No pending questions found; using mock customer questions: {len(questions)}")

    analysis = request_json(
        args.base_url,
        "POST",
        "/governance/analyze",
        {"questions": questions, "top_k": args.top_k},
        args.timeout,
    )
    gaps = analysis.get("gaps", []) or []
    clusters = analysis.get("clusters", []) or []
    drafts = analysis.get("drafts", []) or []
    print(f"Generated gaps: {len(gaps)}")
    print(f"Generated clusters: {len(clusters)}")
    print(f"Generated drafts: {len(drafts)}")

    draft = find_coupon_draft(drafts)
    draft_id = draft["id"]
    print("\nSelected coupon-related draft:")
    print(f"  id: {draft_id}")
    print(f"  title: {draft.get('title')}")
    print(f"  topic: {draft.get('topic')}")

    print_section("3. Approve draft and publish back to Qdrant")
    approved = request_json(args.base_url, "POST", f"/governance/drafts/{draft_id}/approve", timeout=args.timeout)
    print(f"Approved draft id: {approved.get('id')}")
    print(f"Review status: {approved.get('review_status')}")
    print(f"Published chunks: {approved.get('published_chunks')}")

    print_section("4. After governance: ask RAG again")
    after = request_json(
        args.base_url,
        "POST",
        "/rag/ask",
        {
            "question": args.after_question,
            "top_k": args.top_k,
            "session_id": "governance-demo-after",
        },
        args.timeout,
    )
    after_sources = source_names(after)
    passed = has_governance_source(after)
    print(f"Question: {args.after_question}")
    print(f"After answer:\n{compact_answer(after)}")
    print_sources("After sources", after_sources)
    print(f"After sources contains governance_draft: {passed}")

    print_section("5. Demo result")
    print(f"Generated draft id/title/topic: {draft_id} / {draft.get('title')} / {draft.get('topic')}")
    print(f"Verification passed: {passed}")
    if not passed:
        print("Verification failed: /rag/ask did not return a source containing governance_draft.")
        return 2
    return 0


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Demo the governance knowledge loop through local HTTP APIs.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="FastAPI base URL.")
    parser.add_argument(
        "--mock-file", default=str(project_root / "knowledge_base_samples" / "mock_customer_questions.json")
    )
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--after-question", default=AFTER_QUESTION)
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--questions-source",
        choices=["auto", "pending", "mock"],
        default="auto",
        help="Use pending unanswered RAG questions, mock questions, or pending with mock fallback.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        sys.exit(run_demo(parse_args()))
    except DemoError as exc:
        print(f"\nDemo failed: {exc}", file=sys.stderr)
        sys.exit(1)
