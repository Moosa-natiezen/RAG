"""Vector Database Storage Service (Production Qdrant with In-Memory Embedded Fallback)."""

import logging
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings
from app.services.chunking import ChildChunk

logger = logging.getLogger("rag.services.vector_store")


class VectorStoreService:
    """Manages Qdrant collections, HNSW indexing, and RBAC-filtered dense search."""

    def __init__(
        self,
        db_type: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        collection_name: Optional[str] = None,
        dim: Optional[int] = None,
        use_memory: bool = False,
    ):
        self.db_type = db_type or settings.VECTOR_DB_TYPE
        self.host = host or settings.QDRANT_HOST
        self.port = port or settings.QDRANT_PORT
        self.collection_name = collection_name or settings.QDRANT_COLLECTION_NAME
        self.dim = dim or settings.EMBEDDING_DIM
        self.use_memory = use_memory

        self.client: Optional[AsyncQdrantClient] = None
        self._is_embedded: bool = False

    async def initialize(self) -> None:
        """Initialize connection and guarantee collection schema with HNSW index."""
        if not self.use_memory and self.db_type == "qdrant":
            try:
                # Attempt remote Qdrant connection with short timeout
                remote_client = AsyncQdrantClient(
                    host=self.host,
                    port=self.port,
                    api_key=settings.QDRANT_API_KEY,
                    timeout=1.5,
                    check_compatibility=False,
                )
                await remote_client.get_collections()
                self.client = remote_client
                self._is_embedded = False
                logger.info("Connected to remote Qdrant at %s:%d", self.host, self.port)
            except Exception as exc:
                if settings.ENV in {"staging", "production"}:
                    raise RuntimeError("Configured Qdrant vector store is unavailable.") from exc
                logger.info(
                    "Remote Qdrant not reachable at %s:%d. Initializing embedded in-memory Qdrant engine.",
                    self.host,
                    self.port,
                )
                self.client = AsyncQdrantClient(location=":memory:")
                self._is_embedded = True
        else:
            # Explicit in-memory engine
            self.client = AsyncQdrantClient(location=":memory:")
            self._is_embedded = True

        # Ensure collection exists with tuned HNSW indexing
        collections = await self.client.get_collections()
        exists = any(c.name == self.collection_name for c in collections.collections)

        if not exists:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.dim,
                    distance=models.Distance.COSINE,
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                ),
            )
            # Create payload indexes for fast RBAC filtering
            try:
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="access_control_list",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="doc_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception:
                pass  # In-memory engine handles filtering without explicit schema indexes

    @property
    def is_embedded(self) -> bool:
        """Indicates whether running in embedded memory mode or remote server."""
        return self._is_embedded

    async def upsert_chunks(
        self, chunks: List[ChildChunk], vectors: List[List[float]]
    ) -> int:
        """Upsert child chunks and their dense embeddings with metadata payload."""
        if not chunks:
            return 0

        if not self.client:
            await self.initialize()

        points = []
        if len(chunks) != len(vectors):
            raise ValueError("Each child chunk must have exactly one embedding vector.")
        for chunk, vector in zip(chunks, vectors):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.child_id))
            payload = chunk.to_payload()
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        await self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        return len(points)

    async def delete_document(self, doc_id: str) -> None:
        """Remove all indexed child points belonging to a document before replacement."""
        if not self.client:
            await self.initialize()
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="doc_id",
                            match=models.MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
        )

    async def search_dense(
        self,
        query_vector: List[float],
        acl_groups: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Execute RBAC-filtered dense vector similarity search."""
        if not self.client:
            await self.initialize()

        user_acls = acl_groups if acl_groups is not None else ["group_all"]

        query_filter = None
        if user_acls:
            # Match any chunk whose access_control_list contains at least one of user's ACL groups
            query_filter = models.Filter(
                should=[
                    models.FieldCondition(
                        key="access_control_list",
                        match=models.MatchValue(value=acl),
                    )
                    for acl in user_acls
                ]
            )

        # Execute dense vector query
        try:
            response = await self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                search_params=models.SearchParams(hnsw_ef=128),
                with_payload=True,
            )
            hits = response.points
        except Exception:
            hits = await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                search_params=models.SearchParams(hnsw_ef=128),
                with_payload=True,
            )

        results: List[Dict[str, Any]] = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "child_id": payload.get("child_id"),
                    "parent_id": payload.get("parent_id"),
                    "doc_id": payload.get("doc_id"),
                    "section_header": payload.get("section_header"),
                    "text": payload.get("text"),
                    "parent_text": payload.get("parent_text"),
                    "score": hit.score,
                    "metadata": payload,
                }
            )

        return results
