from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.chat_completion import ChatCompletionService
from app.services.hybrid_retriever import HybridRetriever
from app.services.reranker import CrossEncoderReranker


def _document(child_id="child-1", parent_id="parent-1"):
    return {
        "child_id": child_id,
        "parent_id": parent_id,
        "doc_id": "travel_policy",
        "section_header": "Expense deadlines",
        "text": "Submit receipts within 14 business days.",
        "parent_text": "Receipts must be submitted within 14 business days through the Expense Portal.",
        "metadata": {"source_url": "https://intranet/policy"},
    }


class FakeReranker:
    async def rerank(self, query, documents, top_n):
        return documents[:top_n]


class FakeLLM:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    async def generate(self, query, documents, model):
        self.calls += 1
        return self.answer, model or "gpt-4o"


def _retriever(dense, sparse):
    retriever = HybridRetriever(
        vector_store=object(),
        bm25_service=object(),
        embedder=object(),
        rrf_k=60,
        rerank_top_n=30,
    )

    async def retrieve_dual_candidates(query, acl_groups):
        assert all(isinstance(group, str) for group in acl_groups)
        return dense, sparse

    retriever.retrieve_dual_candidates = retrieve_dual_candidates
    return retriever


@pytest.mark.asyncio
async def test_chat_completion_fuses_reranks_and_returns_verified_citations():
    document = _document()
    llm = FakeLLM(
        "Submit receipts within 14 business days. [Doc: travel_policy, Section: Expense deadlines]"
    )
    service = ChatCompletionService(
        retriever=_retriever([document], [document]),
        reranker=FakeReranker(),
        llm=llm,
    )

    response = await service.complete("When are receipts due?", ["group_hr"], 5)

    assert response.fallback is False
    assert response.citations[0].source_url == "https://intranet/policy"
    assert response.citations[0].child_id == "child-1"
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_chat_completion_returns_exact_fallback_when_no_context():
    llm = FakeLLM("should not be called")
    service = ChatCompletionService(
        retriever=_retriever([], []),
        reranker=FakeReranker(),
        llm=llm,
    )

    response = await service.complete("Unknown policy?", ["group_all"], 5)

    assert response.answer == settings.FALLBACK_MESSAGE
    assert response.fallback is True
    assert response.citations == []
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_chat_completion_rejects_answer_with_unknown_citation():
    document = _document()
    llm = FakeLLM("Answer. [Doc: invented, Section: Unknown]")
    service = ChatCompletionService(
        retriever=_retriever([document], []),
        reranker=FakeReranker(),
        llm=llm,
    )

    response = await service.complete("Question?", ["group_all"], 5)

    assert response.answer == settings.FALLBACK_MESSAGE
    assert response.fallback is True


@pytest.mark.asyncio
async def test_cohere_reranker_preserves_provider_order_and_scores(monkeypatch):
    monkeypatch.setattr(settings, "RERANKER_PROVIDER", "cohere")

    class FakeCohereClient:
        async def rerank(self, **kwargs):
            return SimpleNamespace(results=[
                SimpleNamespace(index=1, relevance_score=0.92),
                SimpleNamespace(index=0, relevance_score=0.7),
            ])

    documents = [_document("child-a", "parent-a"), _document("child-b", "parent-b")]
    reranked = await CrossEncoderReranker(FakeCohereClient()).rerank("travel deadline", documents, 2)

    assert [document["child_id"] for document in reranked] == ["child-b", "child-a"]
    assert reranked[0]["relevance_score"] == 0.92