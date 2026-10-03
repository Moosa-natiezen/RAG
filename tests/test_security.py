import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import ASGITransport, AsyncClient

from app.core import security
from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_better_auth_ed25519_jwt_verifies_with_issuer_and_audience(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    class TestJwksClient:
        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key=public_key)

    issuer = settings.BETTER_AUTH_URL.rstrip("/")
    token = jwt.encode(
        {
            "sub": "user-123",
            "iss": issuer,
            "aud": issuer,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "role": "user",
            "accessControlGroups": ["group_all"],
        },
        private_key,
        algorithm="EdDSA",
    )
    monkeypatch.setattr(security, "_jwks_client", lambda url: TestJwksClient())

    claims = await security.verify_better_auth_token(token)

    assert claims["sub"] == "user-123"
    assert claims["accessControlGroups"] == ["group_all"]


@pytest.mark.asyncio
async def test_better_auth_jwt_rejects_wrong_audience(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    issuer = settings.BETTER_AUTH_URL.rstrip("/")

    class TestJwksClient:
        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key=private_key.public_key())

    token = jwt.encode(
        {
            "sub": "user-123",
            "iss": issuer,
            "aud": "https://unexpected.example",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
        },
        private_key,
        algorithm="EdDSA",
    )
    monkeypatch.setattr(security, "_jwks_client", lambda url: TestJwksClient())

    with pytest.raises(security.InvalidBearerToken):
        await security.verify_better_auth_token(token)


@pytest.mark.asyncio
async def test_api_protects_history_and_keeps_status_public():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status_response = await client.get("/api/v1/status")
        history_response = await client.get("/api/v1/chat/history")

    assert status_response.status_code == 200
    assert history_response.status_code == 401
    assert history_response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_api_rejects_invalid_bearer_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/chat/history",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired access token."