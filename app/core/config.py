"""Application configuration management via Pydantic Settings."""

from typing import List, Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production RAG configuration settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Metadata
    PROJECT_NAME: str = "Enterprise Production RAG Pipeline"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENV: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # Security & RBAC
    SECRET_KEY: str = Field(
        default="dev-insecure-secret-key-32-chars-long-change-in-prod!",
        description="HMAC secret key for JWT signing",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: List[str] = ["*"]

    # Vector Storage (Qdrant primary with ChromaDB fallback)
    VECTOR_DB_TYPE: Literal["qdrant", "chroma"] = "qdrant"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "enterprise_knowledge_base"
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"

    # Dense Embeddings (OpenAI text-embedding-3-large)
    OPENAI_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIM: int = 3072

    # Sparse Lexical Search (BM25)
    BM25_PERSIST_PATH: str = "./bm25_index.json"

    # Hybrid Retrieval & RRF Fusion
    RETRIEVAL_LIMIT: int = Field(
        default=100,
        description="Top candidates retrieved independently from dense and sparse indices",
    )
    RRF_K: int = Field(
        default=60,
        description="Smoothing constant for Reciprocal Rank Fusion",
    )

    # Cross-Encoder Re-ranking
    COHERE_API_KEY: Optional[str] = None
    RERANKER_PROVIDER: Literal["cohere", "mock"] = "cohere"
    RERANKER_MODEL: str = "rerank-v3.0"
    RERANK_TOP_N: int = Field(
        default=30,
        description="Number of RRF candidates passed to the cross-encoder re-ranker",
    )
    FINAL_TOP_K: int = Field(
        default=5,
        description="Final number of top ranked chunks passed for prompt assembly",
    )

    # Hierarchical Parent-Child Chunking
    PARENT_CHUNK_SIZE: int = Field(
        default=1000,
        description="Target token size for parent chunks (800-1200 tokens)",
    )
    CHILD_CHUNK_SIZE: int = Field(
        default=250,
        description="Target token size for child chunks (200-300 tokens)",
    )
    CHILD_CHUNK_OVERLAP: int = Field(
        default=50,
        description="Token overlap between consecutive child chunks",
    )

    # LLM Inference & Strict Grounding
    ANTHROPIC_API_KEY: Optional[str] = None
    DEFAULT_LLM_PROVIDER: Literal["openai", "anthropic"] = "openai"
    DEFAULT_LLM_MODEL: str = "gpt-4o"
    FALLBACK_MESSAGE: str = "Information not found in internal knowledge base."
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 1024

    @field_validator("CHILD_CHUNK_SIZE")
    @classmethod
    def validate_chunk_sizes(cls, v: int, info) -> int:
        parent_size = info.data.get("PARENT_CHUNK_SIZE", 1000)
        if v >= parent_size:
            raise ValueError(
                f"CHILD_CHUNK_SIZE ({v}) must be strictly smaller than PARENT_CHUNK_SIZE ({parent_size})"
            )
        return v

    @field_validator("FINAL_TOP_K")
    @classmethod
    def validate_top_k(cls, v: int, info) -> int:
        rerank_top_n = info.data.get("RERANK_TOP_N", 30)
        if v > rerank_top_n:
            raise ValueError(
                f"FINAL_TOP_K ({v}) cannot be greater than RERANK_TOP_N ({rerank_top_n})"
            )
        return v


settings = Settings()
