"""End-to-end hybrid retrieval and grounded chat completion orchestration."""

import logging
import re
import time
from typing import Any

from app.core.config import settings
from app.schemas.response import ChatCompletionResponse, CitationItem
from app.services.llm_service import GroundedLLMService
from app.services.reranker import CrossEncoderReranker
from app.services.hybrid_retriever import HybridRetriever

logger = logging.getLogger("rag.services.chat_completion")
_CITATION_PATTERN = re.compile(r"\[Doc:\s*([^,\]]+),\s*Section:\s*([^\]]+)\]")


class ChatCompletionService:
    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: CrossEncoderReranker | Any,
        llm: GroundedLLMService | Any,
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.llm = llm

    async def complete(
        self,
        query: str,
        acl_groups: list[str],
        top_k: int,
        model: str | None = None,
    ) -> ChatCompletionResponse:
        started = time.perf_counter()
        dense_hits, sparse_hits = await self.retriever.retrieve_dual_candidates(
            query=query,
            acl_groups=acl_groups,
        )
        fused = self.retriever.fuse_rrf(
            dense_results=dense_hits,
            sparse_results=sparse_hits,
            top_n=settings.RERANK_TOP_N,
        )
        reranked = await self.reranker.rerank(query, fused, top_k)
        contexts = self._unique_parent_contexts(reranked)

        if not contexts:
            return self._fallback(started, model)

        answer, used_model = await self.llm.generate(query, contexts, model)
        citations = self._verified_citations(answer, contexts)
        if answer.strip().rstrip(".") == settings.FALLBACK_MESSAGE.rstrip("."):
            return self._fallback(started, used_model)
        if not citations:
            logger.warning("Discarding generated answer without verified inline citations")
            return self._fallback(started, used_model)

        elapsed_ms = (time.perf_counter() - started) * 1000
        return ChatCompletionResponse(
            answer=answer,
            citations=citations,
            latency_ms=round(elapsed_ms, 2),
            model=used_model,
            fallback=False,
        )

    @staticmethod
    def _unique_parent_contexts(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        contexts: list[dict[str, Any]] = []
        seen_parent_ids: set[str] = set()
        for document in documents:
            parent_id = str(document.get("parent_id") or document.get("child_id") or "")
            if parent_id in seen_parent_ids:
                continue
            seen_parent_ids.add(parent_id)
            contexts.append(document)
        return contexts

    @staticmethod
    def _verified_citations(
        answer: str,
        contexts: list[dict[str, Any]],
    ) -> list[CitationItem]:
        by_reference: dict[tuple[str, str], dict[str, Any]] = {}
        for context in contexts:
            reference = (
                str(context.get("doc_id") or ""),
                str(context.get("section_header") or ""),
            )
            if all(reference):
                by_reference[reference] = context

        used_references: list[tuple[str, str]] = []
        for match in _CITATION_PATTERN.finditer(answer):
            reference = (match.group(1).strip(), match.group(2).strip())
            if reference not in by_reference:
                return []
            if reference not in used_references:
                used_references.append(reference)

        if not used_references:
            return []

        for line in answer.splitlines():
            line = line.strip()
            claims = [
                sentence for sentence in re.split(r"(?<=[.!?])\s+", line)
                if _CITATION_PATTERN.sub("", sentence).strip()
            ]
            citations_on_line = len(_CITATION_PATTERN.findall(line))
            if len(claims) > citations_on_line:
                return []

        citations: list[CitationItem] = []
        for doc_id, section_header in used_references:
            context = by_reference[(doc_id, section_header)]
            metadata = context.get("metadata") or {}
            citations.append(
                CitationItem(
                    doc_id=doc_id,
                    section_header=section_header,
                    parent_id=str(context.get("parent_id") or ""),
                    child_id=context.get("child_id"),
                    parent_text=str(context.get("parent_text") or ""),
                    child_text=context.get("text"),
                    title=metadata.get("title"),
                    source_url=metadata.get("source_url"),
                )
            )
        return citations

    @staticmethod
    def _fallback(started: float, model: str | None = None) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            answer=settings.FALLBACK_MESSAGE,
            citations=[],
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            model=model or settings.DEFAULT_LLM_MODEL,
            fallback=True,
        )