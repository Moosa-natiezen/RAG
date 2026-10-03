"""Pydantic schemas for request payloads."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class DocumentIngestTextRequest(BaseModel):
    """Payload schema for ingesting raw textual or markdown documents."""

    doc_id: str = Field(
        ...,
        description="Unique identifier for the document (e.g., hr_policy_2026_v3)",
        examples=["hr_policy_2026_v3"],
    )
    title: str = Field(
        ...,
        description="Human-readable title of the document",
        examples=["Remote Work & Expense Policy 2026"],
    )
    text: str = Field(
        ...,
        description="Full text or markdown contents of the document",
    )
    format: Literal["markdown", "text"] = Field(
        default="markdown",
        description="Text format type for structural parsing",
    )
    access_control_list: List[str] = Field(
        default_factory=lambda: ["group_all"],
        description="RBAC access groups permitted to retrieve this document",
        examples=[["group_hr", "group_all"]],
    )
    source_url: Optional[str] = Field(
        default=None,
        description="Canonical source location or storage URI",
        examples=["s3://internal-docs/hr/2026_v3.pdf"],
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional enterprise metadata attributes",
    )


class ChatCompletionRequest(BaseModel):
    """Payload schema for user query and retrieval generation."""

    query: str = Field(
        ...,
        description="Natural language question or query",
        examples=["What is the deadline for submitting travel expense receipts?"],
    )
    stream: bool = Field(
        default=True,
        description="Whether to stream response tokens via Server-Sent Events (SSE)",
    )
    model: Optional[str] = Field(
        default=None,
        description="LLM model override (defaults to configured model)",
        examples=["gpt-4o", "claude-3-5-sonnet"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of context parent blocks to retrieve for answer generation",
    )
    access_control_list: Optional[List[str]] = Field(
        default=None,
        description="Caller RBAC security groups (if omitted, extracted from JWT token)",
    )
