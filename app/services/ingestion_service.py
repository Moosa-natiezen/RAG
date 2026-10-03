"""Unified Atomic Ingestion Service coordinating parsing, chunking, dense vector upsert, and BM25 indexing."""

import logging
import time
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.schemas.response import IngestResponse
from app.services.bm25_service import BM25Service
from app.services.chunking import HierarchicalChunker
from app.services.embedding import EmbeddingService
from app.services.parser import DocumentParser, DocumentSection
from app.services.vector_store import VectorStoreService

logger = logging.getLogger("rag.services.ingestion")


class IngestionService:
    """Orchestrates atomic dual-indexing pipeline across dense vector store and BM25 index."""

    def __init__(
        self,
        chunker: Optional[HierarchicalChunker] = None,
        embedder: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStoreService] = None,
        bm25_service: Optional[BM25Service] = None,
        persist_sparse_index: bool = False,
    ):
        self.chunker = chunker or HierarchicalChunker()
        self.embedder = embedder or EmbeddingService()
        self.vector_store = vector_store or VectorStoreService()
        self.bm25_service = bm25_service or BM25Service()
        self.persist_sparse_index = persist_sparse_index

    async def ingest_sections(
        self,
        sections: List[DocumentSection],
        doc_id: str,
        title: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestResponse:
        """Atomically chunk, embed, and index parsed document sections into both search engines."""
        start_time = time.perf_counter()
        meta = metadata or {}

        # Step 1: Hierarchical Parent-Child Chunking
        parent_chunks = self.chunker.chunk_document(sections)
        child_chunks = self.chunker.extract_all_child_chunks(parent_chunks)
        total_tokens = sum(p.token_count for p in parent_chunks)

        if not child_chunks:
            raise ValueError("No child chunks generated from provided document sections.")

        # Step 2: Dense Embedding Generation
        child_texts = [c.text for c in child_chunks]
        vectors = await self.embedder.embed_documents(child_texts)
        if len(vectors) != len(child_chunks):
            raise RuntimeError("Embedding provider returned a mismatched number of vectors.")

        # Step 3: Upsert into Qdrant Vector Database
        await self.vector_store.delete_document(doc_id)
        await self.vector_store.upsert_chunks(child_chunks, vectors)

        # Step 4: Index into Sparse BM25 Engine
        self.bm25_service.index_chunks(child_chunks)
        if self.persist_sparse_index:
            self.bm25_service.save()

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        logger.info(
            "Dual-indexing complete for doc_id=%s: %d parents, %d children (%d tokens) indexed in %.2fms",
            doc_id,
            len(parent_chunks),
            len(child_chunks),
            total_tokens,
            elapsed_ms,
        )

        return IngestResponse(
            status="success",
            doc_id=doc_id,
            title=title,
            sections_parsed=len(sections),
            parent_chunks_created=len(parent_chunks),
            child_chunks_created=len(child_chunks),
            total_tokens=total_tokens,
            processing_time_ms=round(elapsed_ms, 2),
            metadata=meta,
        )


# Global shared singleton instance for application runtime
shared_vector_store = VectorStoreService()
shared_bm25_service = BM25Service()
shared_embedder = EmbeddingService()
shared_ingestion_service = IngestionService(
    embedder=shared_embedder,
    vector_store=shared_vector_store,
    bm25_service=shared_bm25_service,
    persist_sparse_index=True,
)
