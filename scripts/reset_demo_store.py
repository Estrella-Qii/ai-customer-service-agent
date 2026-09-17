import sys

from app.core.config import settings
from app.rag.vector_store import reset_collection


def main() -> int:
    deleted = reset_collection()
    if deleted:
        print(f"Deleted Qdrant collection: {settings.qdrant_collection}")
    else:
        print(f"Qdrant collection did not exist: {settings.qdrant_collection}")
    print(
        "Local governance JSON state is ignored by git under data/; "
        "remove it manually if you need a fresh review state."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
