import logging

from fastapi import APIRouter, HTTPException

from app.governance.models import AnalyzeRequest, EditDraftRequest, RejectDraftRequest
from app.governance.service import (
    analyze_questions,
    approve_draft,
    edit_draft,
    list_drafts,
    list_gaps,
    list_unanswered_questions,
    reject_draft,
)

router = APIRouter(prefix="/governance", tags=["Knowledge Governance"])
logger = logging.getLogger(__name__)


@router.post("/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        return analyze_questions(req.questions, req.top_k)
    except Exception as exc:
        logger.exception("Knowledge governance analysis failed")
        raise HTTPException(503, detail="Knowledge governance analysis failed. Check service dependencies.") from exc


@router.get("/gaps")
async def get_gaps():
    return {"gaps": list_gaps()}


@router.get("/drafts")
async def get_drafts():
    return {"drafts": list_drafts()}


@router.get("/unanswered_questions")
async def get_unanswered_questions(status: str = "pending"):
    questions = list_unanswered_questions(status=status)
    return {"questions": questions, "total": len(questions)}


@router.post("/drafts/{draft_id}/approve")
async def approve(draft_id: str):
    try:
        return approve_draft(draft_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Approving governance draft failed")
        raise HTTPException(
            503, detail="Draft publishing failed. Check the embedding and vector-store services."
        ) from exc


@router.post("/drafts/{draft_id}/reject")
async def reject(draft_id: str, req: RejectDraftRequest):
    try:
        return reject_draft(draft_id, req.reason)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@router.post("/drafts/{draft_id}/edit")
async def edit(draft_id: str, req: EditDraftRequest):
    try:
        return edit_draft(draft_id, req)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
