"""Pydantic schemas for API response payloads."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    """Response payload detailing document ingestion and chunking metrics."""

    status: str = Field(default="success", description="Ingestion status")
    doc_id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    sections_parsed: int = Field(
        ..., description="Number of structural sections parsed"
    )
    parent_chunks_created: int = Field(
        ..., description="Number of parent context blocks created (1000 tokens)"
    )
    child_chunks_created: int = Field(
        ..., description="Number of child search units created (250 tokens)"
    )
    total_tokens: int = Field(
        ..., description="Total token volume processed across document"
    )
    processing_time_ms: float = Field(
        ..., description="Wall-clock ingestion time in milliseconds"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Metadata associated with document"
    )


class CitationItem(BaseModel):
    """Detailed attribution reference for verified answer claims."""

    doc_id: str = Field(..., description="Source document ID")
    section_header: str = Field(
        ..., description="Section title or breadcrumb path"
    )
    parent_id: str = Field(..., description="Parent chunk identifier")
    child_id: Optional[str] = Field(
        default=None, description="Matching child chunk ID"
    )
    parent_text: str = Field(
        ..., description="Full parent context block (800-1200 tokens)"
    )
    child_text: Optional[str] = Field(
        default=None,
        description="Specific child excerpt (250 tokens) highlighted in parent",
    )
    source_url: Optional[str] = Field(
        default=None, description="External document URL"
    )


class ChatCompletionResponse(BaseModel):
    """Non-streaming response payload for chat completions."""

    answer: str = Field(
        ..., description="Grounded response text with inline citations"
    )
    citations: List[CitationItem] = Field(
        default_factory=list,
        description="Structured citations corresponding to inline markers",
    )
    latency_ms: float = Field(
        ..., description="Total query execution latency in milliseconds"
    )
    model: str = Field(..., description="Inference model utilized")
    fallback: bool = Field(
        default=False,
        description="True if context was insufficient and fallback response was triggered",
    )
