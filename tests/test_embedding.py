"""Unit tests for Dense Embedding Service."""

import math
import pytest
from app.services.embedding import EmbeddingService


@pytest.mark.asyncio
async def test_embedding_dimensions_and_norm():
    """Verify output vectors match 3072 dimensions and are unit-normalized."""
    service = EmbeddingService(dimensions=3072)
    vector = await service.embed_query("Enterprise travel policy reimbursement")

    assert len(vector) == 3072
    # Verify L2 unit norm (||v|| == 1.0)
    norm = math.sqrt(sum(x * x for x in vector))
    assert pytest.approx(norm, rel=1e-4) == 1.0


@pytest.mark.asyncio
async def test_embedding_determinism():
    """Verify deterministic vector generation for identical strings."""
    service = EmbeddingService(dimensions=3072)
    text = "Section 4.2 - Travel Expense Reimbursement"

    v1 = await service.embed_query(text)
    v2 = await service.embed_query(text)

    assert v1 == v2


@pytest.mark.asyncio
async def test_embedding_different_texts():
    """Verify distinct vectors for different content."""
    service = EmbeddingService(dimensions=3072)
    v1 = await service.embed_query("Security guidelines password rotation")
    v2 = await service.embed_query("Travel meal stipend policy")

    # Cosine similarity between normalized vectors is dot product
    dot_product = sum(a * b for a, b in zip(v1, v2))
    assert dot_product < 0.95


@pytest.mark.asyncio
async def test_batch_embedding():
    """Verify batch embedding generation handles multiple items."""
    service = EmbeddingService(dimensions=3072)
    texts = [f"Policy document chunk number {i}" for i in range(10)]

    vectors = await service.embed_documents(texts, batch_size=4)
    assert len(vectors) == 10
    for vec in vectors:
        assert len(vec) == 3072
