"""Cross-encoder reranking for RRF-fused retrieval candidates."""

import logging
import re
from typing import Any

import cohere

from app.core.config import settings

logger = logging.getLogger("rag.services.reranker")


class RerankerConfigurationError(RuntimeError):
    pass


class RerankerProviderError(RuntimeError):
    pass


class CrossEncoderReranker:
    """Ranks fused documents with Cohere Rerank or an explicit development mock."""

    def __init__(self, client: Any | None = None):
        self.client = client
        if self.client is None and settings.RERANKER_PROVIDER == "cohere" and settings.COHERE_API_KEY:
            self.client = cohere.AsyncClient(api_key=settings.COHERE_API_KEY)

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_n: int,
    ) -> list[dict[str, Any]]:
        if not documents or top_n < 1:
            return []

        if settings.RERANKER_PROVIDER == "mock":
            return self._mock_rerank(query, documents, top_n)
        if self.client is None:
            raise RerankerConfigurationError("COHERE_API_KEY is required for cross-encoder reranking.")

        try:
            response = await self.client.rerank(
                model=settings.RERANKER_MODEL,
                query=query,
                documents=[str(document.get("text") or document.get("parent_text") or "") for document in documents],
                top_n=min(top_n, len(documents)),
            )
        except Exception as exc:
            logger.exception("Cross-encoder reranking failed")
            raise RerankerProviderError("Cross-encoder reranking provider failed.") from exc

        ranked: list[dict[str, Any]] = []
        for result in response.results:
            index = int(result.index)
            if 0 <= index < len(documents):
                document = documents[index].copy()
                document["relevance_score"] = float(result.relevance_score)
                ranked.append(document)
        return ranked

    @staticmethod
    def _mock_rerank(
        query: str,
        documents: list[dict[str, Any]],
        top_n: int,
    ) -> list[dict[str, Any]]:
        query_terms = set(re.findall(r"[\w-]+", query.lower()))
        scored: list[dict[str, Any]] = []
        for document in documents:
            text = f"{document.get('text', '')} {document.get('section_header', '')}"
            document_terms = set(re.findall(r"[\w-]+", text.lower()))
            score = len(query_terms & document_terms) / max(1, len(query_terms))
            if score > 0:
                ranked_document = document.copy()
                ranked_document["relevance_score"] = score
                scored.append(ranked_document)
        scored.sort(key=lambda document: document["relevance_score"], reverse=True)
        return scored[:top_n]