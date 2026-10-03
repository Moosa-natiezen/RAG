"""Document Ingestion API Endpoints with Atomic Dual-Indexing."""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.request import DocumentIngestTextRequest
from app.schemas.response import IngestResponse
from app.services.ingestion_service import shared_ingestion_service
from app.services.parser import DocumentParser

logger = logging.getLogger("rag.api.ingest")
router = APIRouter()


@router.post(
    "/text",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest raw text or markdown document",
)
async def ingest_text_document(payload: DocumentIngestTextRequest) -> IngestResponse:
    """Parse, chunk, embed, and index raw text/Markdown document into Qdrant and BM25."""
    metadata = payload.metadata.copy()
    metadata["title"] = payload.title
    metadata["access_control_list"] = payload.access_control_list
    if payload.source_url:
        metadata["source_url"] = payload.source_url

    # Step 1: Structural parsing
    sections = DocumentParser.parse_markdown(
        text=payload.text,
        doc_id=payload.doc_id,
        base_metadata=metadata,
    )

    if not sections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document content is empty or contains no parseable text.",
        )

    # Step 2: Atomic dual-index ingestion
    try:
        response = await shared_ingestion_service.ingest_sections(
            sections=sections,
            doc_id=payload.doc_id,
            title=payload.title,
            metadata=metadata,
        )
        return response
    except Exception as exc:
        logger.error("Failed to ingest text document %s: %s", payload.doc_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion pipeline failure: {str(exc)}",
        )


@router.post(
    "/file",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest file document (Markdown, DOCX, PDF)",
)
async def ingest_file_document(
    file: UploadFile = File(..., description="Document file to upload"),
    doc_id: str = Form(..., description="Unique document ID"),
    title: Optional[str] = Form(None, description="Document title"),
    access_control_list: Optional[str] = Form(
        None, description="JSON list or comma-separated access control groups"
    ),
    source_url: Optional[str] = Form(None, description="Source URI"),
) -> IngestResponse:
    """Parse, chunk, embed, and index uploaded document (DOCX, PDF, Markdown) into Qdrant and BM25."""
    # Parse ACL groups
    acl: List[str] = ["group_all"]
    if access_control_list:
        try:
            parsed_acl = json.loads(access_control_list)
            if isinstance(parsed_acl, list):
                acl = parsed_acl
            else:
                acl = [str(parsed_acl)]
        except Exception:
            acl = [g.strip() for g in access_control_list.split(",") if g.strip()]

    doc_title = title or file.filename or doc_id
    metadata = {
        "title": doc_title,
        "access_control_list": acl,
        "filename": file.filename,
    }
    if source_url:
        metadata["source_url"] = source_url

    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Step 1: Structural parsing
    try:
        sections = DocumentParser.parse_file(
            file_path_or_bytes=content_bytes,
            filename=file.filename or "doc.txt",
            doc_id=doc_id,
            base_metadata=metadata,
        )
    except Exception as exc:
        logger.error("Error parsing uploaded file %s: %s", file.filename, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse document: {str(exc)}",
        )

    if not sections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text sections extracted from uploaded file.",
        )

    # Step 2: Atomic dual-index ingestion
    try:
        response = await shared_ingestion_service.ingest_sections(
            sections=sections,
            doc_id=doc_id,
            title=doc_title,
            metadata=metadata,
        )
        return response
    except Exception as exc:
        logger.error("Failed to ingest file document %s: %s", doc_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion pipeline failure: {str(exc)}",
        )
