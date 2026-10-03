import json
import logging
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.schemas.request import ChatCompletionRequest
from app.schemas.response import ChatCompletionResponse
from app.services.chat_completion import ChatCompletionService
from app.services.embedding import EmbeddingService
from app.services.hybrid_retriever import HybridRetriever
from app.services.ingestion_service import shared_bm25_service, shared_embedder, shared_vector_store
from app.services.llm_service import LLMConfigurationError, LLMProviderError, GroundedLLMService
from app.services.reranker import CrossEncoderReranker, RerankerConfigurationError, RerankerProviderError

logger = logging.getLogger("rag.api.chat")
router = APIRouter()


@lru_cache(maxsize=1)
def get_chat_completion_service() -> ChatCompletionService:
    retriever = HybridRetriever(
        vector_store=shared_vector_store,
        bm25_service=shared_bm25_service,
        embedder=shared_embedder,
    )
    return ChatCompletionService(
        retriever=retriever,
        reranker=CrossEncoderReranker(),
        llm=GroundedLLMService(),
    )


async def _sse_events(response: ChatCompletionResponse):
    yield {
        "event": "citations",
        "data": json.dumps([citation.model_dump(mode="json") for citation in response.citations]),
    }
    for piece in response.answer.split(" "):
        if piece:
            yield {"event": "token", "data": json.dumps({"text": f"{piece} "})}
    yield {"event": "done", "data": response.model_dump_json()}


@router.post(
    "/completions",
    response_model=None,
    summary="Generate a grounded answer using hybrid retrieval",
    responses={200: {"description": "Grounded JSON response or server-sent event stream."}},
)
async def create_chat_completion(
    payload: ChatCompletionRequest,
    request: Request,
    service: ChatCompletionService = Depends(get_chat_completion_service),
) -> Any:
    claims = request.state.auth["claims"]
    acl_groups = claims.get("accessControlGroups")
    if not isinstance(acl_groups, list) or not all(isinstance(group, str) for group in acl_groups):
        acl_groups = ["group_all"]

    try:
        completion = await service.complete(
            query=payload.query,
            acl_groups=acl_groups,
            top_k=min(payload.top_k, settings.FINAL_TOP_K),
            model=payload.model,
        )
    except (RerankerConfigurationError, LLMConfigurationError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except (RerankerProviderError, LLMProviderError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Chat completion pipeline failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Chat completion failed.") from exc

    if payload.stream:
        return EventSourceResponse(_sse_events(completion))
    return completion