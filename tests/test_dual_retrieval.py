"""Unit tests for Concurrent Dual Retrieval Driver."""

import pytest
from app.services.bm25_service import BM25Service
from app.services.chunking import ChildChunk
from app.services.embedding import EmbeddingService
from app.services.hybrid_retriever import HybridRetriever
from app.services.vector_store import VectorStoreService


@pytest.mark.asyncio
async def test_concurrent_dual_retrieval():
    """Verify concurrent retrieval dispatches both dense and sparse searches."""
    vector_store = VectorStoreService(collection_name="test_dual_coll", dim=3072)
    await vector_store.initialize()

    bm25 = BM25Service()
    embedder = EmbeddingService(dimensions=3072)

    chunks = [
        ChildChunk(
            child_id="c_policy_code",
            parent_id="p_pol",
            doc_id="sec_01",
            section_header="Access Control",
            text="Service accounts must authenticate using SEC-TOKEN-V2 credentials.",
            token_count=10,
            parent_text="Full security specification for SEC-TOKEN-V2.",
            metadata={"access_control_list": ["group_sec", "group_all"]},
        ),
        ChildChunk(
            child_id="c_pto_rules",
            parent_id="p_pto",
            doc_id="hr_02",
            section_header="Paid Time Off",
            text="Employees receive 20 days of paid vacation annually.",
            token_count=9,
            parent_text="Full employee benefits document.",
            metadata={"access_control_list": ["group_hr", "group_all"]},
        ),
    ]

    # Index into both engines
    vectors = await embedder.embed_documents([c.text for c in chunks])
    await vector_store.upsert_chunks(chunks, vectors)
    bm25.index_chunks(chunks)

    retriever = HybridRetriever(
        vector_store=vector_store,
        bm25_service=bm25,
        embedder=embedder,
        retrieval_limit=10,
    )

    # Search for exact token
    dense_hits, sparse_hits = await retriever.retrieve_dual_candidates(
        query="SEC-TOKEN-V2", acl_groups=["group_all"]
    )

    assert len(dense_hits) >= 1
    assert len(sparse_hits) >= 1
    assert sparse_hits[0]["child_id"] == "c_policy_code"


@pytest.mark.asyncio
async def test_dual_retrieval_rbac_isolation():
    """Verify RBAC filtering applies strictly across both retrievers simultaneously."""
    vector_store = VectorStoreService(collection_name="test_dual_rbac", dim=3072)
    await vector_store.initialize()

    bm25 = BM25Service()
    embedder = EmbeddingService(dimensions=3072)

    restricted_chunk = ChildChunk(
        child_id="c_finance_audit",
        parent_id="p_fin",
        doc_id="fin_audit_2026",
        section_header="Q3 Financial Audit",
        text="Audit code AUDIT-FIN-992 requires CFO signoff.",
        token_count=9,
        parent_text="Restricted audit findings.",
        metadata={"access_control_list": ["group_finance_leads"]},
    )

    vectors = await embedder.embed_documents([restricted_chunk.text])
    await vector_store.upsert_chunks([restricted_chunk], vectors)
    bm25.index_chunks([restricted_chunk])

    retriever = HybridRetriever(
        vector_store=vector_store,
        bm25_service=bm25,
        embedder=embedder,
    )

    # Query with unauthorized groups
    dense_hits, sparse_hits = await retriever.retrieve_dual_candidates(
        query="AUDIT-FIN-992", acl_groups=["group_all", "group_engineering"]
    )
    assert len(dense_hits) == 0
    assert len(sparse_hits) == 0

    # Query with authorized group
    auth_dense, auth_sparse = await retriever.retrieve_dual_candidates(
        query="AUDIT-FIN-992", acl_groups=["group_finance_leads"]
    )
    assert len(auth_dense) == 1
    assert len(auth_sparse) == 1
    assert auth_dense[0]["child_id"] == "c_finance_audit"
    assert auth_sparse[0]["child_id"] == "c_finance_audit"
