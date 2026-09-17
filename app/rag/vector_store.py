import logging
from functools import lru_cache
from typing import Any

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings
from app.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)

COLLECTION_NAME = settings.qdrant_collection


class QdrantConnectionError(RuntimeError):
    pass


class CollectionDimensionError(RuntimeError):
    pass


class EmbeddingConfigurationError(RuntimeError):
    pass


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        timeout=10,
        check_compatibility=False,
        trust_env=False,
    )


def _qdrant_connection_message(exc: Exception) -> str:
    return (
        f"Qdrant connection failed at {settings.qdrant_url}. "
        "When running FastAPI on Windows and Qdrant in Docker, use QDRANT_URL=http://127.0.0.1:6333 "
        "and start it with: docker compose up -d qdrant redis. "
        f"Original error: {type(exc).__name__}: {exc}"
    )


def _get_collections(client: QdrantClient) -> list[str]:
    try:
        return [collection.name for collection in client.get_collections().collections]
    except Exception as exc:
        logger.exception("Failed to connect to Qdrant at %s", settings.qdrant_url)
        raise QdrantConnectionError(_qdrant_connection_message(exc)) from exc


def collection_exists(client: QdrantClient) -> bool:
    return COLLECTION_NAME in _get_collections(client)


@lru_cache
def get_embedding_dimension() -> int:
    if settings.embedding_dimension > 0:
        return settings.embedding_dimension

    try:
        vector = get_embeddings().embed_query("dimension probe")
    except Exception as exc:
        logger.exception("Failed to obtain embedding dimension from model %s", settings.embedding_model)
        raise EmbeddingConfigurationError(
            "Embedding failed while detecting vector dimension. "
            "Check SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL and EMBEDDING_MODEL. "
            f"Current EMBEDDING_MODEL={settings.embedding_model}. "
            f"Original error: {type(exc).__name__}: {exc}"
        ) from exc

    if not vector:
        raise EmbeddingConfigurationError("Embedding API returned an empty vector while detecting dimension.")
    return len(vector)


def _vector_size_from_config(vectors_config: Any) -> int | None:
    if vectors_config is None:
        return None

    size = getattr(vectors_config, "size", None)
    if size is not None:
        return int(size)

    if isinstance(vectors_config, dict):
        if "size" in vectors_config:
            return int(vectors_config["size"])
        for value in vectors_config.values():
            nested_size = _vector_size_from_config(value)
            if nested_size is not None:
                return nested_size

    return None


def get_collection_vector_size(client: QdrantClient) -> int | None:
    try:
        info = client.get_collection(COLLECTION_NAME)
    except Exception as exc:
        logger.exception("Failed to inspect Qdrant collection %s", COLLECTION_NAME)
        raise QdrantConnectionError(_qdrant_connection_message(exc)) from exc

    vectors_config = getattr(getattr(info.config, "params", None), "vectors", None)
    return _vector_size_from_config(vectors_config)


def ensure_collection(client: QdrantClient) -> None:
    """Create the Qdrant collection if needed and validate vector dimension."""
    expected_dim = get_embedding_dimension()

    if not collection_exists(client):
        logger.info(
            "Creating Qdrant collection %s with vector dimension %s for embedding model %s",
            COLLECTION_NAME,
            expected_dim,
            settings.embedding_model,
        )
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=expected_dim, distance=Distance.COSINE),
        )
        return

    actual_dim = get_collection_vector_size(client)
    if actual_dim is not None and actual_dim != expected_dim:
        raise CollectionDimensionError(
            f"Qdrant collection '{COLLECTION_NAME}' vector dimension is {actual_dim}, "
            f"but current embedding model '{settings.embedding_model}' produces {expected_dim}. "
            "Reset the demo collection before uploading documents again. "
            "Run: .\\.venv\\Scripts\\python.exe scripts\\reset_demo_store.py"
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

    try:
        ids = vector_store.add_documents(chunks)
    except CollectionDimensionError:
        raise
    except Exception as exc:
        logger.exception("Failed to embed or store documents in Qdrant collection %s", COLLECTION_NAME)
        raise RuntimeError(
            "Embedding or Qdrant write failed. "
            f"Check EMBEDDING_MODEL={settings.embedding_model}, SILICONFLOW_API_KEY, "
            f"and QDRANT_URL={settings.qdrant_url}. "
            f"Original error: {type(exc).__name__}: {exc}"
        ) from exc
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
    if not collection_exists(client):
        return []

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
    if not collection_exists(client):
        return 0

    point_ids = []
    for point in _scroll_all_points(client):
        if _payload_source_file(point.payload or {}) == filename:
            point_ids.append(point.id)

    if not point_ids:
        return 0

    client.delete(collection_name=COLLECTION_NAME, points_selector=point_ids)
    return len(point_ids)


def reset_collection() -> bool:
    """Delete the configured demo collection if it exists."""
    client = get_qdrant_client()
    if not collection_exists(client):
        return False
    client.delete_collection(COLLECTION_NAME)
    get_embedding_dimension.cache_clear()
    return True


def get_vector_store() -> QdrantVectorStore:
    """Return a searchable Qdrant vector store."""
    client = get_qdrant_client()
    ensure_collection(client)
    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=get_embeddings(),
    )
