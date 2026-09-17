import logging
import os
import traceback
from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.rag.document_loader import load_and_split
from app.rag.retriever import retrieve
from app.rag.vector_store import (
    CollectionDimensionError,
    EmbeddingConfigurationError,
    QdrantConnectionError,
    add_documents,
    delete_document,
    document_exists,
    list_documents,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Document Management"])


def _log_exception(context: str, exc: Exception) -> None:
    logger.error("%s failed: %s: %s", context, type(exc).__name__, exc)
    logger.debug("Traceback for %s:\n%s", context, traceback.format_exc())


def _http_500(context: str, exc: Exception) -> HTTPException:
    _log_exception(context, exc)
    if isinstance(exc, QdrantConnectionError):
        return HTTPException(status_code=503, detail="Qdrant is unavailable. Check the service and QDRANT_URL.")
    elif isinstance(exc, CollectionDimensionError):
        return HTTPException(
            status_code=409,
            detail="The Qdrant collection vector size does not match the configured embedding model.",
        )
    elif isinstance(exc, EmbeddingConfigurationError):
        return HTTPException(status_code=503, detail="The embedding provider is unavailable or misconfigured.")
    elif "Embedding" in type(exc).__name__ or "embedding" in str(exc).lower():
        return HTTPException(status_code=503, detail="The embedding request failed.")
    return HTTPException(status_code=500, detail=f"{context.capitalize()} failed. See server logs for details.")


def _safe_filename(filename: str | None) -> str:
    normalized = (filename or "").replace("\\", "/")
    safe_name = PurePosixPath(normalized).name.strip()
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(400, detail="A valid filename is required")
    if len(safe_name) > 255:
        raise HTTPException(400, detail="Filename is too long")
    return safe_name


async def _read_upload_with_limit(file: UploadFile) -> bytes:
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        max_mb = settings.max_upload_bytes / (1024 * 1024)
        raise HTTPException(413, detail=f"File exceeds the {max_mb:g} MB upload limit")
    return data


@router.post("/upload")
async def upload_document(file: Annotated[UploadFile, File()]):
    """Upload a document, split it, embed chunks and store them in Qdrant."""
    allowed = [".pdf", ".txt", ".md"]
    filename = _safe_filename(file.filename)
    suffix = os.path.splitext(filename)[-1].lower()
    if suffix not in allowed:
        raise HTTPException(400, detail=f"Only {allowed} files are supported, got {suffix or 'no extension'}")

    file_bytes = await _read_upload_with_limit(file)
    if not file_bytes:
        raise HTTPException(400, detail="Uploaded file is empty")

    try:
        replaced = document_exists(filename)
        if replaced:
            delete_document(filename)

        chunks = load_and_split(file_bytes, filename)
        count = add_documents(chunks)
    except Exception as exc:
        raise _http_500("document upload", exc) from exc

    return {
        "filename": filename,
        "chunks_stored": count,
        "replaced": replaced,
        "message": "Document was embedded and stored in the knowledge base.",
    }


@router.get("")
async def get_documents():
    try:
        documents = list_documents()
    except Exception as exc:
        raise _http_500("document list", exc) from exc

    return {"documents": documents, "total": len(documents)}


@router.delete("/{filename}")
async def remove_document(filename: str):
    try:
        deleted_chunks = delete_document(filename)
    except Exception as exc:
        raise _http_500("document delete", exc) from exc

    if deleted_chunks == 0:
        raise HTTPException(404, detail=f"Document not found: {filename}")

    return {
        "filename": filename,
        "deleted_chunks": deleted_chunks,
        "message": "Document was deleted from the knowledge base.",
    }


@router.get("/search")
async def search_documents(q: str, top_k: int = 4):
    if not q.strip():
        raise HTTPException(400, detail="Search query cannot be empty")
    if top_k < 1 or top_k > 20:
        raise HTTPException(400, detail="top_k must be between 1 and 20")

    try:
        results = retrieve(q, top_k)
    except Exception as exc:
        raise _http_500("document search", exc) from exc
    return {"query": q, "results": results}
