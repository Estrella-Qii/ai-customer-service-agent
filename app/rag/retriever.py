from app.rag.vector_store import get_vector_store


def retrieve(query: str, top_k: int = 4) -> list[dict]:
    """Return the most relevant chunks for a user query."""
    vs = get_vector_store()
    results = vs.similarity_search_with_score(query, k=top_k)

    return [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source_file", "unknown"),
            "chunk_index": doc.metadata.get("chunk_index"),
            "score": round(float(score), 4),
        }
        for doc, score in results
    ]
