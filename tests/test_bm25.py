"""Unit tests for Sparse Lexical Search Service (BM25)."""

import os
from pathlib import Path
import pytest
from app.services.bm25_service import BM25Service
from app.services.chunking import ChildChunk


@pytest.fixture
def sample_chunks():
    return [
        ChildChunk(
            child_id="c_err_code",
            parent_id="p_err",
            doc_id="error_spec",
            section_header="Authentication Errors",
            text="When JWT validation fails, the service returns ERR-401-EXPIRED.",
            token_count=12,
            parent_text="Full authentication specification: ERR-401-EXPIRED details.",
            metadata={"access_control_list": ["group_engineering", "group_all"]},
        ),
        ChildChunk(
            child_id="c_travel_rules",
            parent_id="p_travel",
            doc_id="hr_policy_2026",
            section_header="Travel Expense Stipend",
            text="Employees receive a $75 daily meal stipend during overseas travel.",
            token_count=12,
            parent_text="Full travel expense document.",
            metadata={"access_control_list": ["group_hr", "group_all"]},
        ),
        ChildChunk(
            child_id="c_confidential_merger",
            parent_id="p_merger",
            doc_id="corp_dev",
            section_header="Project Falcon",
            text="Project Falcon acquisition targets confidential data.",
            token_count=8,
            parent_text="Full M&A document.",
            metadata={"access_control_list": ["group_executive"]},
        ),
    ]


def test_bm25_exact_code_matching(sample_chunks):
    """Verify BM25 retrieves exact code match with highest score."""
    service = BM25Service()
    service.index_chunks(sample_chunks)

    results = service.search_sparse("ERR-401-EXPIRED", acl_groups=["group_all"])
    assert len(results) >= 1
    top_hit = results[0]
    assert top_hit["child_id"] == "c_err_code"
    assert "ERR-401-EXPIRED" in top_hit["text"]
    assert top_hit["score"] > 0


def test_bm25_rbac_filtering(sample_chunks):
    """Verify BM25 excludes chunks outside user's ACL groups."""
    service = BM25Service()
    service.index_chunks(sample_chunks)

    # Search with standard employee ACL (no group_executive)
    results = service.search_sparse(
        "Project Falcon acquisition", acl_groups=["group_all", "group_engineering"]
    )
    assert len(results) == 0

    # Search with executive ACL
    results = service.search_sparse(
        "Project Falcon acquisition", acl_groups=["group_executive"]
    )
    assert len(results) == 1
    assert results[0]["child_id"] == "c_confidential_merger"


def test_bm25_save_and_load(sample_chunks, tmp_path):
    """Verify index state can be saved and restored from disk."""
    save_file = str(tmp_path / "test_bm25.json")
    service1 = BM25Service(persist_path=save_file)
    service1.index_chunks(sample_chunks)
    service1.save()

    assert os.path.exists(save_file)

    service2 = BM25Service(persist_path=save_file)
    loaded = service2.load()
    assert loaded is True
    assert len(service2.corpus_chunks) == len(sample_chunks)

    results = service2.search_sparse("meal stipend allowance", acl_groups=["group_all"])
    assert len(results) >= 1
    assert results[0]["child_id"] == "c_travel_rules"
