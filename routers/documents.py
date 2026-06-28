import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.rag.document_loader import load_and_split
from app.rag.retriever import retrieve
from app.rag.vector_store import add_documents

router = APIRouter(prefix="/documents", tags=["文档管理"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档 -> 自动切片 -> 向量化 -> 存入 Qdrant."""
    allowed = [".pdf", ".txt", ".md"]
    suffix = os.path.splitext(file.filename or "")[-1].lower()
    if suffix not in allowed:
        raise HTTPException(400, detail=f"只支持 {allowed}，收到 {suffix or '无后缀文件'}")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(400, detail="上传文件为空")

    try:
        chunks = load_and_split(file_bytes, file.filename or "uploaded_file")
        count = add_documents(chunks)
    except Exception as exc:
        raise HTTPException(500, detail=f"处理失败: {exc}") from exc

    return {
        "filename": file.filename,
        "chunks_stored": count,
        "message": "文档已成功向量化入库",
    }


@router.get("/search")
async def search_documents(q: str, top_k: int = 4):
    if not q.strip():
        raise HTTPException(400, detail="搜索关键词不能为空")
    if top_k < 1 or top_k > 20:
        raise HTTPException(400, detail="top_k 必须在 1 到 20 之间")

    results = retrieve(q, top_k)
    return {"query": q, "results": results}
