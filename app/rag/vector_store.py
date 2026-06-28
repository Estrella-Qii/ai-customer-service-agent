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


def get_vector_store() -> QdrantVectorStore:
    """Return a searchable Qdrant vector store."""
    client = get_qdrant_client()
    ensure_collection(client)
    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=get_embeddings(),
    )
