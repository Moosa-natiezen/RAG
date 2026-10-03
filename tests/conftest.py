import time

import pytest

from app.core import security
from app.core.config import settings


@pytest.fixture
def mock_better_auth(monkeypatch):
    async def verify_token(token: str):
        if token != "test-token":
            raise security.InvalidBearerToken
        return {
            "sub": "test-user",
            "sessionId": "test-session",
            "iss": settings.BETTER_AUTH_URL.rstrip("/"),
            "aud": settings.BETTER_AUTH_URL.rstrip("/"),
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "accessControlGroups": ["group_all"],
        }

    async def record_claims(request, claims):
        return None

    monkeypatch.setattr(security, "verify_better_auth_token", verify_token)
    monkeypatch.setattr(security, "_record_claims", record_claims)