import logging
import chromadb
from app.config import settings

logger = logging.getLogger(__name__)

_client = None
_collection = None


def get_vector_store():
    global _client, _collection
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        _collection = _client.get_or_create_collection(
            name="products",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB initialized at %s", settings.CHROMA_PERSIST_DIR)
    return _collection


def upsert_product(product) -> None:
    col = get_vector_store()
    doc_text = f"{product.title}. {product.description}"
    col.upsert(
        ids=[product.vector_id],
        documents=[doc_text],
        metadatas=[
            {
                "product_id": product.id,
                "category": product.category,
                "price": float(product.price),
                "title": product.title,
            }
        ],
    )


def delete_product(vector_id: str) -> None:
    col = get_vector_store()
    try:
        col.delete(ids=[vector_id])
    except Exception as exc:
        logger.warning("ChromaDB delete failed for %s: %s", vector_id, exc)


def search_products(query: str, n_results: int = 10, category_filter: str | None = None):
    col = get_vector_store()
    count = col.count()
    if count == 0:
        return []
    n = min(n_results, count)
    kwargs: dict = {"query_texts": [query], "n_results": n}
    if category_filter:
        kwargs["where"] = {"category": category_filter}
    try:
        results = col.query(**kwargs)
    except Exception as exc:
        logger.error("ChromaDB query failed: %s", exc)
        return []

    ids = results["ids"][0] if results["ids"] else []
    metas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []
    return [
        {"vector_id": vid, "distance": dist, **meta}
        for vid, meta, dist in zip(ids, metas, distances)
    ]
