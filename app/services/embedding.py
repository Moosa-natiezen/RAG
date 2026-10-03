"""OpenAI Dense Embedding Client Service with Async Batching & Fallbacks."""

import hashlib
import logging
import math
from typing import List, Optional

import httpx
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger("rag.services.embedding")


class EmbeddingService:
    """Async dense embedding service with 3072-dim vectors and offline fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.EMBEDDING_MODEL
        self.dimensions = dimensions or settings.EMBEDDING_DIM

        # Configure persistent HTTP/2 client for low-latency connection pooling
        if self.api_key and self.api_key != "your-openai-api-key-here":
            http_client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(15.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )
            self.client: Optional[AsyncOpenAI] = AsyncOpenAI(
                api_key=self.api_key,
                http_client=http_client,
                max_retries=3,
            )
        else:
            self.client = None
            if settings.ENV in {"staging", "production"}:
                raise RuntimeError("OPENAI_API_KEY is required for embeddings outside development/test.")
            logger.info(
                "OpenAI API key not configured or in test mode. Utilizing deterministic mock embedding generator."
            )

    async def embed_query(self, text: str) -> List[float]:
        """Generate normalized embedding vector for single search query."""
        results = await self.embed_documents([text])
        return results[0]

    async def embed_documents(
        self, texts: List[str], batch_size: int = 64
    ) -> List[List[float]]:
        """Generate normalized dense embeddings in batches."""
        if not texts:
            return []

        clean_texts = [t.replace("\n", " ").strip() or " " for t in texts]

        # Use live OpenAI API if client is configured
        if self.client:
            try:
                all_embeddings: List[List[float]] = []
                for i in range(0, len(clean_texts), batch_size):
                    batch = clean_texts[i : i + batch_size]
                    response = await self.client.embeddings.create(
                        input=batch,
                        model=self.model,
                        dimensions=self.dimensions,
                    )
                    batch_vectors = [item.embedding for item in response.data]
                    all_embeddings.extend(batch_vectors)
                return all_embeddings
            except Exception as exc:
                logger.exception("OpenAI embedding request failed")
                raise RuntimeError("OpenAI embedding provider failed.") from exc

        # Deterministic offline mock generator for development & CI
        return [
            self.generate_deterministic_vector(t, dim=self.dimensions)
            for t in clean_texts
        ]

    @staticmethod
    def generate_deterministic_vector(text: str, dim: int = 3072) -> List[float]:
        """Produce reproducible, unit-normalized dense vector from text hash."""
        # Use sha512 iterations to generate pseudo-random coordinates
        vector: List[float] = []
        seed = text.encode("utf-8")
        block_idx = 0

        while len(vector) < dim:
            h = hashlib.sha512(seed + f":blk:{block_idx}".encode("utf-8")).digest()
            # Convert 64 bytes into 16 floats
            for i in range(0, len(h) - 3, 4):
                val = int.from_bytes(h[i : i + 4], byteorder="big", signed=True)
                vector.append(val / 2147483648.0)
                if len(vector) == dim:
                    break
            block_idx += 1

        # L2-normalize vector to unit length
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]

        return vector
