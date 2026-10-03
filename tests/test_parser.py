"""Unit tests for AST and structural document parser."""

import os
from pathlib import Path
import pytest
from app.services.parser import DocumentParser, DocumentSection


def test_markdown_parsing_hierarchy():
    """Verify markdown sections preserve heading paths and hierarchy."""
    sample_md = """# Enterprise Policy Manual
Introductory text before any sub-heading.

## Section 1: Code of Conduct
All employees must maintain professionalism.

### 1.1 Confidentiality
Proprietary company data must remain encrypted.

### 1.2 Remote Work Standards
Workspaces must be secure and private.

## Section 2: Expense Policy
Reimbursement rules for travel.
"""
    sections = DocumentParser.parse_markdown(sample_md, doc_id="policy_v1")
    assert len(sections) == 5

    # Check top-level intro
    assert sections[0].section_header == "Enterprise Policy Manual"
    assert "Introductory text" in sections[0].content

    # Check subsection
    sub_sec = sections[2]
    assert sub_sec.header_path == [
        "Enterprise Policy Manual",
        "Section 1: Code of Conduct",
        "1.1 Confidentiality",
    ]
    assert (
        sub_sec.section_header
        == "Enterprise Policy Manual > Section 1: Code of Conduct > 1.1 Confidentiality"
    )
    assert "Proprietary company data" in sub_sec.content


def test_markdown_fallback_no_headers():
    """Verify fallback for text without headers."""
    sample_text = "This is a single paragraph document with no headers."
    sections = DocumentParser.parse_markdown(sample_text, doc_id="plain_doc")
    assert len(sections) == 1
    assert sections[0].content == sample_text
    assert sections[0].section_header == "Document Body"


def test_docx_parsing_with_existing_file():
    """Verify DOCX parsing on real project files."""
    docx_path = Path("Product Requirements Document.docx")
    if docx_path.exists():
        sections = DocumentParser.parse_file(
            docx_path,
            filename="Product Requirements Document.docx",
            doc_id="prd_2026",
            base_metadata={"author": "Product"},
        )
        assert len(sections) > 0
        assert all(isinstance(s, DocumentSection) for s in sections)
        assert sections[0].doc_id == "prd_2026"
        assert sections[0].metadata["author"] == "Product"


def test_parse_file_bytes_input():
    """Verify byte stream parsing."""
    raw_md_bytes = b"# Byte Title\nByte content here."
    sections = DocumentParser.parse_file(
        raw_md_bytes,
        filename="test.md",
        doc_id="bytes_doc",
    )
    assert len(sections) == 1
    assert sections[0].section_header == "Byte Title"
    assert "Byte content here." in sections[0].content
