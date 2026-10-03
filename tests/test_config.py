"""Unit tests for application configuration and validation."""

import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_default_settings():
    """Verify default architectural specifications."""
    settings = Settings()
    assert settings.PROJECT_NAME == "Enterprise Production RAG Pipeline"
    assert settings.EMBEDDING_MODEL == "text-embedding-3-large"
    assert settings.EMBEDDING_DIM == 3072
    assert settings.RRF_K == 60
    assert settings.RETRIEVAL_LIMIT == 100
    assert settings.RERANK_TOP_N == 30
    assert settings.FINAL_TOP_K == 5
    assert settings.PARENT_CHUNK_SIZE == 1000
    assert settings.CHILD_CHUNK_SIZE == 250
    assert settings.CHILD_CHUNK_OVERLAP == 50
    assert settings.FALLBACK_MESSAGE == "Information not found in internal knowledge base"


def test_chunk_size_validation():
    """Verify that child chunk size must be smaller than parent chunk size."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(PARENT_CHUNK_SIZE=500, CHILD_CHUNK_SIZE=600)
    assert "CHILD_CHUNK_SIZE (600) must be strictly smaller than PARENT_CHUNK_SIZE (500)" in str(
        exc_info.value
    )


def test_top_k_validation():
    """Verify that FINAL_TOP_K cannot exceed RERANK_TOP_N."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(RERANK_TOP_N=10, FINAL_TOP_K=15)
    assert "FINAL_TOP_K (15) cannot be greater than RERANK_TOP_N (10)" in str(
        exc_info.value
    )


def test_env_override():
    """Verify environment variable overrides work."""
    settings = Settings(
        ENV="production",
        QDRANT_HOST="qdrant.internal",
        FINAL_TOP_K=8,
    )
    assert settings.ENV == "production"
    assert settings.QDRANT_HOST == "qdrant.internal"
    assert settings.FINAL_TOP_K == 8
