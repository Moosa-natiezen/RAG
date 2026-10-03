import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.response import ChatCompletionResponse, CitationItem
from app.api.v1.endpoints.chat import get_chat_completion_service


class FakeChatCompletionService:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _response(fallback=False):
    citations = [] if fallback else [
        CitationItem(
            doc_id="travel_policy",
            section_header="Expense deadlines",
            parent_id="parent-1",
            child_id="child-1",
            parent_text="Receipts are due in 14 business days.",
            child_text="Submit receipts within 14 business days.",
        )
    ]
    return ChatCompletionResponse(
        answer=(
            "Information not found in internal knowledge base"
            if fallback
            else "Submit receipts within 14 business days. [Doc: travel_policy, Section: Expense deadlines]"
        ),
        citations=citations,
        latency_ms=12.5,
        model="gpt-4o",
        fallback=fallback,
    )


@pytest.mark.asyncio
async def test_chat_completion_json_uses_jwt_acl_not_request_acl(mock_better_auth):
    service = FakeChatCompletionService(_response())
    app.dependency_overrides[get_chat_completion_service] = lambda: service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        ) as client:
            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "query": "When are receipts due?",
                    "stream": False,
                    "access_control_list": ["group_executive"],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["fallback"] is False
    assert response.json()["citations"][0]["doc_id"] == "travel_policy"
    assert service.calls[0]["acl_groups"] == ["group_all"]


@pytest.mark.asyncio
async def test_chat_completion_stream_emits_fallback_and_done_events(mock_better_auth):
    service = FakeChatCompletionService(_response(fallback=True))
    app.dependency_overrides[get_chat_completion_service] = lambda: service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        ) as client:
            response = await client.post(
                "/api/v1/chat/completions",
                json={"query": "Unknown question", "stream": True},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "Information not found in internal knowledge base" in response.text
    assert "event: done" in response.text


@pytest.mark.asyncio
async def test_chat_completion_requires_bearer_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/completions",
            json={"query": "What is our policy?", "stream": False},
        )

    assert response.status_code == 401


def test_grounded_citations_must_exist_in_retrieved_context():
    from app.services.chat_completion import ChatCompletionService

    context = [{
        "doc_id": "travel_policy",
        "section_header": "Expense deadlines",
        "parent_id": "parent-1",
        "child_id": "child-1",
        "parent_text": "Submit receipts within 14 business days.",
        "text": "Receipts are due in 14 business days.",
        "metadata": {},
    }]

    citations = ChatCompletionService._verified_citations(
        "Submit receipts within 14 business days. [Doc: travel_policy, Section: Expense deadlines]",
        context,
    )
    invalid = ChatCompletionService._verified_citations(
        "Submit receipts within 14 business days. [Doc: invented, Section: Unknown]",
        context,
    )

    assert len(citations) == 1
    assert invalid == []