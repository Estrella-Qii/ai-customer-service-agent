import os
import tempfile

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SEPARATORS = ["\n\n", "\n", "\u3002", "\uff1b", "\uff0c", ".", "!", "?", " "]


def _build_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=CHUNK_SEPARATORS,
    )


def load_and_split(file_bytes: bytes, filename: str) -> list[Document]:
    """Load uploaded file bytes and return split LangChain documents."""
    suffix = os.path.splitext(filename)[-1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        if suffix == ".pdf":
            loader = PyPDFLoader(tmp_path)
        elif suffix in [".txt", ".md"]:
            loader = TextLoader(tmp_path, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

        docs = loader.load()
    finally:
        os.unlink(tmp_path)

    chunks = _build_splitter().split_documents(docs)
    for index, chunk in enumerate(chunks):
        chunk.metadata["source_file"] = filename
        chunk.metadata["chunk_index"] = index

    return chunks


def split_text_to_documents(text: str, source_file: str, metadata: dict | None = None) -> list[Document]:
    """Split generated knowledge text into LangChain documents."""
    base_metadata = {"source_file": source_file, **(metadata or {})}
    docs = _build_splitter().split_documents([Document(page_content=text, metadata=base_metadata)])
    for index, doc in enumerate(docs):
        doc.metadata["chunk_index"] = index
    return docs
