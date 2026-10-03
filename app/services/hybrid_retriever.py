"""Hybrid Dual Retrieval Driver coordinating concurrent search and Reciprocal Rank Fusion (RRF)."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.bm25_service import BM25Service
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStoreService

logger = logging.getLogger("rag.services.hybrid_retriever")


class HybridRetriever:
    """Dispatches concurrent retrieval across Qdrant and BM25, fusing candidates using RRF (k=60)."""

    def __init__(
        self,
        vector_store: Optional[VectorStoreService] = None,
        bm25_service: Optional[BM25Service] = None,
        embedder: Optional[EmbeddingService] = None,
        retrieval_limit: Optional[int] = None,
        rrf_k: Optional[int] = None,
        rerank_top_n: Optional[int] = None,
    ):
        self.vector_store = vector_store or VectorStoreService()
        self.bm25_service = bm25_service or BM25Service()
        self.embedder = embedder or EmbeddingService()
        self.retrieval_limit = retrieval_limit or settings.RETRIEVAL_LIMIT
        self.rrf_k = rrf_k or settings.RRF_K
        self.rerank_top_n = rerank_top_n or settings.RERANK_TOP_N

    async def retrieve_dual_candidates(
        self,
        query: str,
        acl_groups: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Execute concurrent dense and sparse candidate search restricted by RBAC ACLs."""
        start_time = time.perf_counter()
        search_limit = limit or self.retrieval_limit
        user_acls = acl_groups if acl_groups is not None else ["group_all"]

        # Step 1: Query embedding generation
        query_vector = await self.embedder.embed_query(query)

        # Step 2: Concurrent dual dispatch via asyncio.gather
        dense_task = asyncio.create_task(
            self.vector_store.search_dense(
                query_vector=query_vector,
                acl_groups=user_acls,
                limit=search_limit,
            )
        )

        sparse_task = asyncio.create_task(
            asyncio.to_thread(
                self.bm25_service.search_sparse,
                query=query,
                acl_groups=user_acls,
                limit=search_limit,
            )
        )

        dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        logger.info(
            "Dual retrieval completed in %.2fms | Dense candidates: %d | Sparse candidates: %d",
            elapsed_ms,
            len(dense_results),
            len(sparse_results),
        )

        return dense_results, sparse_results

    def fuse_rrf(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        k: Optional[int] = None,
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Merge dense and sparse result lists using Reciprocal Rank Fusion: RRF = sum(1 / (k + rank))."""
        k_constant = k or self.rrf_k
        cutoff = top_n or self.rerank_top_n

        rrf_scores: Dict[str, float] = {}
        child_to_doc: Dict[str, Dict[str, Any]] = {}
        retriever_ranks: Dict[str, Dict[str, int]] = {}

        # Accumulate RRF scores for dense candidates
        for rank, hit in enumerate(dense_results, start=1):
            child_id = hit["child_id"]
            reciprocal_score = 1.0 / (k_constant + rank)
            rrf_scores[child_id] = rrf_scores.get(child_id, 0.0) + reciprocal_score
            child_to_doc[child_id] = hit
            retriever_ranks.setdefault(child_id, {})["dense_rank"] = rank

        # Accumulate RRF scores for sparse candidates
        for rank, hit in enumerate(sparse_results, start=1):
            child_id = hit["child_id"]
            reciprocal_score = 1.0 / (k_constant + rank)
            rrf_scores[child_id] = rrf_scores.get(child_id, 0.0) + reciprocal_score
            if child_id not in child_to_doc:
                child_to_doc[child_id] = hit
            retriever_ranks.setdefault(child_id, {})["sparse_rank"] = rank

        # Sort candidate child IDs descending by combined RRF score
        sorted_candidates = sorted(
            rrf_scores.items(), key=lambda item: item[1], reverse=True
        )[:cutoff]

        fused_documents: List[Dict[str, Any]] = []
        for child_id, score in sorted_candidates:
            doc = child_to_doc[child_id].copy()
            doc["rrf_score"] = round(score, 6)
            doc["ranks"] = retriever_ranks.get(child_id, {})
            fused_documents.append(doc)

        logger.info(
            "RRF Fusion merged %d dense + %d sparse hits into %d candidates (cutoff=%d, k=%d)",
            len(dense_results),
            len(sparse_results),
            len(fused_documents),
            cutoff,
            k_constant,
        )

        return fused_documents

    async def search_hybrid_candidates(
        self,
        query: str,
        acl_groups: Optional[List[str]] = None,
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Convenience method: execute dual retrieval and return RRF-fused candidate list."""
        dense_hits, sparse_hits = await self.retrieve_dual_candidates(
            query=query, acl_groups=acl_groups
        )
        return self.fuse_rrf(
            dense_results=dense_hits, sparse_results=sparse_hits, top_n=top_n
        )
