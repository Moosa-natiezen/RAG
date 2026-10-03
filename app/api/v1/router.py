"""API v1 Central Router."""

from fastapi import APIRouter
from app.api.v1.endpoints import history, ingest

api_router = APIRouter()

# Mount endpoints
api_router.include_router(
    ingest.router, prefix="/documents/ingest", tags=["Ingestion"]
)
api_router.include_router(history.router, prefix="/chat/history", tags=["Chat History"])


@api_router.get("/status", tags=["System"])
async def get_api_status():
    """Retrieve operational status of API v1."""
    return {"status": "active", "version": "v1"}
