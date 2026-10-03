"""Unit tests for Hierarchical Parent-Child Chunking Engine."""

import pytest
from app.services.chunking import HierarchicalChunker, ChildChunk, ParentChunk
from app.services.parser import DocumentSection


def test_token_counter():
    """Verify tokenizer counts tokens using tiktoken cl100k_base."""
    chunker = HierarchicalChunker()
    count = chunker.count_tokens("Hello world! This is an enterprise test.")
    assert count > 0
    assert count < 20


def test_small_section_parent_child():
    """Verify small section produces 1 parent and appropriate child chunks."""
    chunker = HierarchicalChunker(
        parent_chunk_size=500, child_chunk_size=100, child_chunk_overlap=20
    )
    section = DocumentSection(
        title="Travel Reimbursement",
        header_path=["Policies", "Travel"],
        content="Employees are eligible for a daily meal stipend of up to $75. Receipts must be submitted within 14 business days.",
        section_header="Policies > Travel",
        doc_id="hr_policy_2026",
        metadata={"access_control_list": ["group_hr", "group_all"]},
    )

    parents = chunker.chunk_section(section)
    assert len(parents) == 1
    parent = parents[0]
    assert parent.doc_id == "hr_policy_2026"
    assert parent.section_header == "Policies > Travel"
    assert len(parent.children) >= 1

    # Check child properties
    child = parent.children[0]
    assert child.parent_id == parent.parent_id
    assert child.parent_text == parent.text
    assert child.metadata["access_control_list"] == ["group_hr", "group_all"]


def test_large_section_multi_parents():
    """Verify large sections are partitioned across multiple overlapping parent chunks."""
    chunker = HierarchicalChunker(
        parent_chunk_size=100, child_chunk_size=40, child_chunk_overlap=10
    )
    # Generate long text (~300 tokens)
    long_text = "Enterprise RAG hybrid search pipeline. " * 60
    section = DocumentSection(
        title="Long Spec",
        header_path=["Architecture"],
        content=long_text,
        section_header="Architecture",
        doc_id="arch_spec",
        metadata={"dept": "engineering"},
    )

    parents = chunker.chunk_section(section)
    assert len(parents) > 1

    # Check that each parent has children and parent_text matching
    for parent in parents:
        assert parent.token_count <= 100
        assert len(parent.children) >= 1
        for child in parent.children:
            assert child.parent_id == parent.parent_id
            assert child.parent_text == parent.text
            assert child.metadata["dept"] == "engineering"


def test_extract_all_child_chunks():
    """Verify flattening of child chunks across multiple sections."""
    chunker = HierarchicalChunker(
        parent_chunk_size=300, child_chunk_size=50, child_chunk_overlap=10
    )
    sections = [
        DocumentSection(
            title="Sec 1",
            header_path=["H1"],
            content="Content for section 1 with enough text to generate multiple words and tokens.",
            section_header="H1",
            doc_id="doc_1",
        ),
        DocumentSection(
            title="Sec 2",
            header_path=["H2"],
            content="Content for section 2 with another paragraph of text for testing.",
            section_header="H2",
            doc_id="doc_1",
        ),
    ]

    parents = chunker.chunk_document(sections)
    all_children = chunker.extract_all_child_chunks(parents)

    assert len(parents) == 2
    assert len(all_children) >= 2
    for child in all_children:
        assert isinstance(child, ChildChunk)
        payload = child.to_payload()
        assert "child_id" in payload
        assert "parent_id" in payload
        assert "parent_text" in payload
