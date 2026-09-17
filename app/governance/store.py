import json
import threading
from pathlib import Path

from app.governance.models import (
    GapCluster,
    GovernanceState,
    KnowledgeDraft,
    KnowledgeGap,
    ReviewAction,
    ReviewRecord,
    ReviewStatus,
    UnansweredQuestion,
    utc_now,
)

STORE_PATH = Path("data/governance_store.json")


def _state_from_data(data: dict) -> GovernanceState:
    if hasattr(GovernanceState, "model_validate"):
        return GovernanceState.model_validate(data)
    return GovernanceState.parse_obj(data)


def _state_to_data(state: GovernanceState) -> dict:
    if hasattr(state, "model_dump"):
        return state.model_dump(mode="json")
    return state.dict()


class GovernanceStore:
    def __init__(self, path: Path = STORE_PATH) -> None:
        self.path = path
        self._lock = threading.RLock()

    def load(self) -> GovernanceState:
        with self._lock:
            if not self.path.exists():
                return GovernanceState()

            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            return _state_from_data(data)

    def save(self, state: GovernanceState) -> GovernanceState:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            with temp_path.open("w", encoding="utf-8") as file:
                json.dump(_state_to_data(state), file, ensure_ascii=False, indent=2)
                file.flush()
            temp_path.replace(self.path)
            return state

    def replace_analysis(
        self,
        gaps: list[KnowledgeGap],
        clusters: list[GapCluster],
        drafts: list[KnowledgeDraft],
    ) -> GovernanceState:
        with self._lock:
            state = self.load()
            state.gaps = gaps
            state.clusters = clusters
            reviewed_drafts = [draft for draft in state.drafts if draft.review_status != ReviewStatus.pending]
            state.drafts = reviewed_drafts + drafts
            return self.save(state)

    def get_draft(self, draft_id: str) -> KnowledgeDraft | None:
        for draft in self.load().drafts:
            if draft.id == draft_id:
                return draft
        return None

    def update_draft(self, draft: KnowledgeDraft, action: ReviewAction, reason: str | None = None) -> GovernanceState:
        with self._lock:
            state = self.load()
            for index, current in enumerate(state.drafts):
                if current.id == draft.id:
                    draft.updated_at = utc_now()
                    state.drafts[index] = draft
                    state.review_history.append(ReviewRecord(draft_id=draft.id, action=action, reason=reason))
                    return self.save(state)
            raise KeyError(f"Draft not found: {draft.id}")

    def mark_rejected(self, draft_id: str, reason: str) -> KnowledgeDraft:
        with self._lock:
            draft = self.get_draft(draft_id)
            if draft is None:
                raise KeyError(f"Draft not found: {draft_id}")
            if draft.review_status == ReviewStatus.approved:
                raise ValueError("Published drafts cannot be rejected. Remove the published document first.")
            draft.review_status = ReviewStatus.rejected
            draft.rejection_reason = reason
            self.update_draft(draft, ReviewAction.reject, reason)
            return draft

    def add_unanswered_question(self, item: UnansweredQuestion) -> GovernanceState:
        with self._lock:
            state = self.load()
            for existing in state.unanswered_questions:
                if (
                    existing.status == "pending"
                    and existing.question == item.question
                    and existing.session_id == item.session_id
                ):
                    existing.timestamp = item.timestamp
                    existing.top_sources = item.top_sources
                    existing.top_score = item.top_score
                    existing.answer = item.answer
                    return self.save(state)

            state.unanswered_questions.append(item)
            return self.save(state)


governance_store = GovernanceStore()
