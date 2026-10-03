"""Integration tests for FastAPI base application and health endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_healthz():
    """Verify liveness probe returns HTTP 200."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "environment" in data


@pytest.mark.asyncio
async def test_readyz():
    """Verify readiness probe returns HTTP 200."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/readyz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "vector_store" in data


@pytest.mark.asyncio
async def test_root():
    """Verify root documentation entrypoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_api_v1_status():
    """Verify API v1 router responds under /api/v1/status."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["version"] == "v1"


@pytest.mark.asyncio
async def test_openapi_schema():
    """Verify OpenAPI specification is generated properly."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert schema["info"]["title"] == "Enterprise Production RAG Pipeline"
