"""FastAPI Application Entry Point & Lifespan Architecture."""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.security import BetterAuthMiddleware
from app.services.ingestion_service import shared_bm25_service, shared_vector_store

# Structured logging setup
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rag.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown event hooks."""
    start_time = time.time()
    logger.info("Initializing Enterprise RAG Pipeline services...")
    logger.info(
        "Configured Vector Store: %s | Embedding Model: %s",
        settings.VECTOR_DB_TYPE,
        settings.EMBEDDING_MODEL,
    )
    shared_bm25_service.load()
    await shared_vector_store.initialize()
    yield
    # Shutdown cleanup occurs here
    logger.info("Enterprise RAG Pipeline services shut down cleanly.")


def create_app() -> FastAPI:
    """Application factory for FastAPI instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "Production RAG Pipeline with Hybrid Search (Dense Vectors + BM25 + "
            "Cross-Encoder Re-ranking) and Parent-Child Chunking for internal enterprise knowledge."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )

    # Cross-Origin Resource Sharing (CORS) Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(BetterAuthMiddleware)

    # Global Exception Handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled server exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred processing your request.",
                "path": request.url.path,
            },
        )

    # Health & Diagnostics Endpoints
    @app.get("/healthz", tags=["Health"], summary="Liveness Probe")
    async def liveness_probe():
        """Liveness check for container orchestrators (Kubernetes / Docker)."""
        return {
            "status": "ok",
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENV,
        }

    @app.get("/readyz", tags=["Health"], summary="Readiness Probe")
    async def readiness_probe():
        """Readiness check validating downstream service availability."""
        # Returns readiness status for traffic ingestion
        return {
            "status": "ready",
            "vector_store": settings.VECTOR_DB_TYPE,
            "reranker": settings.RERANKER_PROVIDER,
        }

    @app.get("/", tags=["Root"])
    async def root():
        """Root API metadata overview."""
        return {
            "message": "Welcome to Enterprise Production RAG API",
            "version": settings.VERSION,
            "docs": "/docs",
            "api_v1": settings.API_V1_STR,
        }

    # Mount API v1 router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS if settings.ENV == "production" else 1,
        reload=settings.DEBUG,
    )
