from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings
from app.rag.embeddings import get_embeddings

COLLECTION_NAME = settings.qdrant_collection
VECTOR_DIM = 1024


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection(client: QdrantClient) -> None:
    """Create the Qdrant collection if it does not exist."""
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )


def add_documents(chunks: list[Document]) -> int:
    """Embed chunks and store them in Qdrant."""
    client = get_qdrant_client()
    ensure_collection(client)

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=get_embeddings(),
    )

    ids = vector_store.add_documents(chunks)
    return len(ids)


def _payload_source_file(payload: dict | None) -> str | None:
    if not payload:
        return None

    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata.get("source_file"):
        return str(metadata["source_file"])

    if payload.get("source_file"):
        return str(payload["source_file"])

    return None


def _payload_chunk_index(payload: dict | None) -> int | None:
    if not payload:
        return None

    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata.get("chunk_index") is not None:
        return int(metadata["chunk_index"])

    if payload.get("chunk_index") is not None:
        return int(payload["chunk_index"])

    return None


def _payload_content(payload: dict | None) -> str:
    if not payload:
        return ""
    return str(payload.get("page_content") or payload.get("content") or "")


def _scroll_all_points(client: QdrantClient):
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        yield from points
        if offset is None:
            break


def list_documents() -> list[dict]:
    """Return document summaries grouped by source file."""
    client = get_qdrant_client()
    ensure_collection(client)

    documents: dict[str, dict] = {}
    for point in _scroll_all_points(client):
        payload = point.payload or {}
        source_file = _payload_source_file(payload)
        if not source_file:
            continue

        item = documents.setdefault(
            source_file,
            {
                "filename": source_file,
                "chunks": 0,
                "chunk_indexes": [],
                "preview": "",
            },
        )
        item["chunks"] += 1

        chunk_index = _payload_chunk_index(payload)
        if chunk_index is not None:
            item["chunk_indexes"].append(chunk_index)

        if not item["preview"]:
            item["preview"] = _payload_content(payload)[:160]

    for item in documents.values():
        item["chunk_indexes"] = sorted(set(item["chunk_indexes"]))

    return sorted(documents.values(), key=lambda doc: doc["filename"])


def document_exists(filename: str) -> bool:
    return any(item["filename"] == filename for item in list_documents())


def delete_document(filename: str) -> int:
    """Delete all chunks that belong to a source file."""
    client = get_qdrant_client()
    ensure_collection(client)

    point_ids = []
    for point in _scroll_all_points(client):
        if _payload_source_file(point.payload or {}) == filename:
            point_ids.append(point.id)

    if not point_ids:
        return 0

    client.delete(collection_name=COLLECTION_NAME, points_selector=point_ids)
    return len(point_ids)


def get_vector_store() -> QdrantVectorStore:
    """Return a searchable Qdrant vector store."""
    client = get_qdrant_client()
    ensure_collection(client)
    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=get_embeddings(),
    )
