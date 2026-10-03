"""Unit tests for Atomic Dual-Index Ingestion Service."""

import pytest
from app.services.bm25_service import BM25Service
from app.services.chunking import HierarchicalChunker
from app.services.embedding import EmbeddingService
from app.services.ingestion_service import IngestionService
from app.services.parser import DocumentSection
from app.services.vector_store import VectorStoreService


@pytest.mark.asyncio
async def test_atomic_dual_indexing_pipeline():
    """Verify sections are chunked, embedded, and indexed across both vector store and BM25."""
    vector_store = VectorStoreService(collection_name="test_ingest_coll", dim=3072)
    await vector_store.initialize()

    bm25 = BM25Service()
    embedder = EmbeddingService(dimensions=3072)
    chunker = HierarchicalChunker(parent_chunk_size=500, child_chunk_size=100)

    service = IngestionService(
        chunker=chunker,
        embedder=embedder,
        vector_store=vector_store,
        bm25_service=bm25,
    )

    sections = [
        DocumentSection(
            title="HR Remote Work Guidelines",
            header_path=["HR", "Remote Work"],
            content=(
                "Remote employees are eligible for home office equipment stipends. "
                "The maximum reimbursement is $1,200 annually under clause HR-REMOTE-2026."
            ),
            section_header="HR > Remote Work",
            doc_id="hr_remote_2026",
            metadata={"access_control_list": ["group_hr", "group_all"]},
        ),
    ]

    response = await service.ingest_sections(
        sections=sections,
        doc_id="hr_remote_2026",
        title="HR Remote Work Guidelines",
        metadata={"category": "benefits"},
    )

    assert response.status == "success"
    assert response.doc_id == "hr_remote_2026"
    assert response.sections_parsed == 1
    assert response.parent_chunks_created >= 1
    assert response.child_chunks_created >= 1

    # Verify search in dense vector store
    query_vec = await embedder.embed_query("office equipment reimbursement")
    dense_hits = await vector_store.search_dense(
        query_vec, acl_groups=["group_all"], limit=5
    )
    assert len(dense_hits) >= 1
    assert dense_hits[0]["doc_id"] == "hr_remote_2026"

    # Verify search in sparse BM25 index for exact clause code
    bm25_hits = bm25.search_sparse("HR-REMOTE-2026", acl_groups=["group_all"], limit=5)
    assert len(bm25_hits) >= 1
    assert bm25_hits[0]["doc_id"] == "hr_remote_2026"
    assert "HR-REMOTE-2026" in bm25_hits[0]["text"]

    # Verify both indices share the same child chunk ID
    assert dense_hits[0]["child_id"] == bm25_hits[0]["child_id"]
