"""
DocuMind 2.0 — Tenant-Isolated Qdrant Client
Every user gets their own collection. Zero cross-tenant data leakage.
"""

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    VectorParams,
    SparseVector,
    SparseVectorParams,
    NamedSparseVector,
    NamedVector,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams,
    ScoredPoint,
)
from loguru import logger

from app.config import settings


class TenantQdrantClient:
    """
    Qdrant client with per-user collection namespacing.
    Each user's documents are stored in collection 'user_{user_id}_documents'.
    This ensures complete data isolation between tenants.

    Supports two modes:
    - 'remote': connects to an external Qdrant server (docker-compose)
    - 'local': uses on-disk storage (HF Spaces / single container)
    """

    def __init__(self):
        if settings.QDRANT_MODE == "local":
            import os
            os.makedirs(settings.QDRANT_LOCAL_PATH, exist_ok=True)
            logger.info(f"Qdrant running in LOCAL mode at: {settings.QDRANT_LOCAL_PATH}")
            self.client = AsyncQdrantClient(
                path=settings.QDRANT_LOCAL_PATH,
            )
            self._sync_client = QdrantClient(
                path=settings.QDRANT_LOCAL_PATH,
            )
        else:
            logger.info(f"Qdrant connecting to REMOTE server: {settings.QDRANT_URL}")
            self.client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY or None,
                timeout=30,
            )
            self._sync_client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY or None,
                timeout=30,
            )

    def get_collection_name(self, user_id: str) -> str:
        """Get the Qdrant collection name for a specific user."""
        return f"user_{user_id}_documents"

    async def ensure_collection(self, user_id: str) -> None:
        """
        Create the user's collection if it doesn't exist.
        Configures both dense (cosine) and sparse (BM25) vector indices.
        """
        collection_name = self.get_collection_name(user_id)
        try:
            collections = await self.client.get_collections()
            existing_names = [c.name for c in collections.collections]

            if collection_name not in existing_names:
                await self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "dense": VectorParams(
                            size=settings.EMBEDDING_DIMENSION,
                            distance=Distance.COSINE,
                        )
                    },
                    sparse_vectors_config={
                        "bm25": SparseVectorParams()
                    },
                )
                logger.info(f"Created Qdrant collection: {collection_name}")
            else:
                logger.debug(f"Collection already exists: {collection_name}")

        except Exception as e:
            logger.error(f"Failed to ensure collection {collection_name}: {e}")
            raise

    async def upsert_chunks(
        self,
        user_id: str,
        chunks: list[dict],
    ) -> None:
        """
        Upsert document chunks with both dense and sparse vectors.

        Each chunk dict must contain:
        - id: str (unique chunk ID)
        - dense_vector: list[float] (embedding)
        - sparse_indices: list[int] (BM25 token indices)
        - sparse_values: list[float] (BM25 token weights)
        - text: str (chunk text)
        - metadata: dict (page_number, document_id, chunk_type, etc.)
        """
        collection_name = self.get_collection_name(user_id)
        await self.ensure_collection(user_id)

        points = []
        for chunk in chunks:
            point = PointStruct(
                id=chunk["id"],
                vector={
                    "dense": chunk["dense_vector"],
                },
                payload={
                    "text": chunk["text"],
                    "document_id": chunk["metadata"].get("document_id", ""),
                    "page_number": chunk["metadata"].get("page_number"),
                    "chunk_type": chunk["metadata"].get("chunk_type", "unknown"),
                    "source_file": chunk["metadata"].get("source_file", ""),
                    "element_id": chunk["metadata"].get("element_id", ""),
                    "table_html": chunk["metadata"].get("table_html"),
                    "sub_chunk_index": chunk["metadata"].get("sub_chunk_index"),
                },
            )

            # Add sparse vector if available
            if chunk.get("sparse_indices") and chunk.get("sparse_values"):
                point.vector["bm25"] = SparseVector(
                    indices=chunk["sparse_indices"],
                    values=chunk["sparse_values"],
                )

            points.append(point)

        # Batch upsert (max 100 points per batch)
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            await self.client.upsert(
                collection_name=collection_name,
                points=batch,
            )

        logger.info(
            f"Upserted {len(points)} chunks to collection {collection_name}"
        )

    async def search_dense(
        self,
        user_id: str,
        query_vector: list[float],
        document_ids: list[str] | None = None,
        limit: int = 20,
    ) -> list[ScoredPoint]:
        """
        Dense vector search in user's collection.
        Optionally filter by specific document IDs.
        """
        collection_name = self.get_collection_name(user_id)

        query_filter = None
        if document_ids:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=doc_id),
                    )
                    for doc_id in document_ids
                ]
            )

        results = await self.client.search(
            collection_name=collection_name,
            query_vector=NamedVector(name="dense", vector=query_vector),
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            search_params=SearchParams(hnsw_ef=128, exact=False),
        )

        return results

    async def get_all_chunks(
        self,
        user_id: str,
        document_ids: list[str] | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """
        Fetch all chunk texts and metadata for BM25 scoring.
        Used by the hybrid retriever's sparse search component.
        """
        collection_name = self.get_collection_name(user_id)

        scroll_filter = None
        if document_ids:
            scroll_filter = Filter(
                should=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=doc_id),
                    )
                    for doc_id in document_ids
                ]
            )

        points, _ = await self.client.scroll(
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            limit=limit,
            with_payload=True,
            with_vectors=True,
        )

        return [
            {
                "id": str(point.id),
                "text": point.payload.get("text", ""),
                "metadata": {
                    "document_id": point.payload.get("document_id"),
                    "page_number": point.payload.get("page_number"),
                    "chunk_type": point.payload.get("chunk_type"),
                    "source_file": point.payload.get("source_file"),
                },
                "dense_vector": point.vector.get("dense") if isinstance(point.vector, dict) else None,
            }
            for point in points
        ]

    async def delete_document_chunks(self, user_id: str, document_id: str) -> None:
        """Delete all chunks belonging to a specific document."""
        collection_name = self.get_collection_name(user_id)

        await self.client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )
        logger.info(f"Deleted chunks for document {document_id} from {collection_name}")

    async def delete_collection(self, user_id: str) -> None:
        """Delete the entire user collection. Use with extreme caution."""
        collection_name = self.get_collection_name(user_id)
        await self.client.delete_collection(collection_name=collection_name)
        logger.warning(f"Deleted entire collection: {collection_name}")

    async def get_collection_info(self, user_id: str) -> dict:
        """Get collection info (point count, status, etc.)."""
        collection_name = self.get_collection_name(user_id)
        try:
            info = await self.client.get_collection(collection_name=collection_name)
            return {
                "name": collection_name,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": info.status.value,
            }
        except Exception:
            return {"name": collection_name, "points_count": 0, "status": "not_found"}


# ── Singleton ──────────────────────────────────────────────────
qdrant_client = TenantQdrantClient()
