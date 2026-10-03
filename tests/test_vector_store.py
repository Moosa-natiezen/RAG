"""Unit tests for Vector Database Storage Service and RBAC filtering."""

import pytest
from app.services.chunking import ChildChunk
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStoreService


@pytest.mark.asyncio
async def test_vector_store_upsert_and_search():
    """Verify upserting child chunks and performing dense similarity search."""
    store = VectorStoreService(collection_name="test_dense_coll", dim=3072)
    await store.initialize()

    embedder = EmbeddingService(dimensions=3072)

    chunks = [
        ChildChunk(
            child_id="c_travel_1",
            parent_id="p_travel",
            doc_id="hr_policy",
            section_header="Travel Reimbursement",
            text="Employees are eligible for a $75 daily meal stipend.",
            token_count=12,
            parent_text="Full travel reimbursement policy details: $75 meal stipend.",
            metadata={"access_control_list": ["group_hr", "group_all"]},
        ),
        ChildChunk(
            child_id="c_security_1",
            parent_id="p_security",
            doc_id="sec_policy",
            section_header="Password Rotation",
            text="Passwords must be rotated every 90 days across internal systems.",
            token_count=11,
            parent_text="Full IT security policy details: 90 days rotation.",
            metadata={"access_control_list": ["group_sec"]},
        ),
    ]

    vectors = await embedder.embed_documents([c.text for c in chunks])
    count = await store.upsert_chunks(chunks, vectors)
    assert count == 2

    # Query for travel
    query_vec = await embedder.embed_query("meal stipend allowance")
    results = await store.search_dense(
        query_vec, acl_groups=["group_all"], limit=5
    )

    assert len(results) >= 1
    hit = results[0]
    assert hit["child_id"] == "c_travel_1"
    assert hit["parent_id"] == "p_travel"
    assert "75" in hit["parent_text"]


@pytest.mark.asyncio
async def test_rbac_access_control_filtering():
    """Verify RBAC filtering prevents unauthorized users from retrieving restricted chunks."""
    store = VectorStoreService(collection_name="test_rbac_coll", dim=3072)
    await store.initialize()

    embedder = EmbeddingService(dimensions=3072)

    confidential_chunk = ChildChunk(
        child_id="c_exec_salary",
        parent_id="p_exec",
        doc_id="exec_comp",
        section_header="Executive Compensation",
        text="Executive bonus structure is confidential to board members.",
        token_count=10,
        parent_text="Full executive compensation document.",
        metadata={"access_control_list": ["group_board_only"]},
    )

    vector = await embedder.embed_query(confidential_chunk.text)
    await store.upsert_chunks([confidential_chunk], [vector])

    # Search with unauthorized groups (regular employee)
    query_vec = await embedder.embed_query("executive bonus compensation")
    unauthorized_hits = await store.search_dense(
        query_vec, acl_groups=["group_all", "group_engineering"], limit=5
    )
    assert len(unauthorized_hits) == 0

    # Search with authorized group (board member)
    authorized_hits = await store.search_dense(
        query_vec, acl_groups=["group_board_only"], limit=5
    )
    assert len(authorized_hits) == 1
    assert authorized_hits[0]["child_id"] == "c_exec_salary"
