"""Integration tests for document ingestion API endpoints."""

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_ingest_text_document_success():
    """Verify raw text/markdown ingestion produces valid parent and child metrics."""
    payload = {
        "doc_id": "it_sec_policy",
        "title": "IT Security Guideline",
        "text": (
            "# IT Security Policy\n"
            "## Password Requirements\n"
            "Mandatory password rotations occur every 90 days.\n"
            "## MFA Policy\n"
            "Multi-factor authentication is required for all systems."
        ),
        "format": "markdown",
        "access_control_list": ["group_it", "group_all"],
        "metadata": {"confidentiality": "internal"},
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/documents/ingest/text", json=payload
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["doc_id"] == "it_sec_policy"
        assert data["sections_parsed"] >= 2
        assert data["parent_chunks_created"] >= 2
        assert data["child_chunks_created"] >= 2
        assert data["total_tokens"] > 0
        assert data["processing_time_ms"] > 0


@pytest.mark.asyncio
async def test_ingest_text_document_empty():
    """Verify empty text rejected with HTTP 400."""
    payload = {
        "doc_id": "empty_doc",
        "title": "Empty Document",
        "text": "   ",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/documents/ingest/text", json=payload
        )
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_ingest_file_markdown():
    """Verify file upload ingestion for Markdown."""
    file_content = b"# HR Travel Reimbursement\nEmployees eligible for $75 daily meal stipend."

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/documents/ingest/file",
            data={
                "doc_id": "hr_travel_2026",
                "title": "Travel Policy",
                "access_control_list": '["group_hr", "group_all"]',
            },
            files={"file": ("travel_policy.md", file_content, "text/markdown")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["doc_id"] == "hr_travel_2026"
        assert data["sections_parsed"] >= 1
        assert data["parent_chunks_created"] >= 1


@pytest.mark.asyncio
async def test_ingest_file_docx_real():
    """Verify real enterprise DOCX file ingestion."""
    docx_path = Path("Enterprise.docx")
    if docx_path.exists():
        with open(docx_path, "rb") as f:
            file_bytes = f.read()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/documents/ingest/file",
                data={
                    "doc_id": "enterprise_design_docx",
                    "title": "Enterprise UI/UX Design",
                },
                files={
                    "file": (
                        "Enterprise.docx",
                        file_bytes,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["doc_id"] == "enterprise_design_docx"
            assert data["parent_chunks_created"] > 0
            assert data["child_chunks_created"] > 0
