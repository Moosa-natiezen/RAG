import logging
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWKClientError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.db.models import AuthClaimAudit
from app.db.session import get_session_factory

logger = logging.getLogger("rag.auth")


class InvalidBearerToken(Exception):
    pass


class BetterAuthUnavailable(Exception):
    pass


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)


async def verify_better_auth_token(token: str) -> dict[str, Any]:
    if token.count(".") != 2:
        raise InvalidBearerToken
    issuer = settings.BETTER_AUTH_URL.rstrip("/")
    try:
        client = _jwks_client(settings.BETTER_AUTH_JWKS_URL)
        key = await run_in_threadpool(client.get_signing_key_from_jwt, token)
    except PyJWKClientConnectionError as exc:
        raise BetterAuthUnavailable from exc
    except PyJWKClientError as exc:
        raise InvalidBearerToken from exc
    except jwt.PyJWTError as exc:
        raise InvalidBearerToken from exc

    try:
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["EdDSA"],
            issuer=issuer,
            audience=issuer,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidBearerToken from exc

    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise InvalidBearerToken
    return claims


async def _record_claims(request: Request, claims: dict[str, Any]) -> None:
    try:
        factory = get_session_factory()
        async with factory() as session:
            session.add(
                AuthClaimAudit(
                    user_id=claims["sub"],
                    session_id=claims.get("sessionId"),
                    claims=claims,
                    method=request.method,
                    path=request.url.path,
                )
            )
            await session.commit()
    except Exception as exc:
        logger.exception("Unable to persist verified JWT claims")
        raise BetterAuthUnavailable from exc


class BetterAuthMiddleware(BaseHTTPMiddleware):
    """Protect API routes with Better Auth-issued, JWKS-verified access tokens."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        public_paths = {
            "/api/v1/status",
            "/api/v1/openapi.json",
        }
        if request.method == "OPTIONS" or not path.startswith("/api/v1/") or path in public_paths:
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return JSONResponse(
                status_code=401,
                content={"detail": "A valid Better Auth Bearer token is required."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            claims = await verify_better_auth_token(token.strip())
            await _record_claims(request, claims)
        except InvalidBearerToken:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired access token."},
                headers={"WWW-Authenticate": "Bearer"},
            )
        except BetterAuthUnavailable:
            return JSONResponse(
                status_code=503,
                content={"detail": "Authentication or audit storage is temporarily unavailable."},
            )

        request.state.auth = {
            "user_id": claims["sub"],
            "session_id": claims.get("sessionId"),
            "claims": claims,
        }
        return await call_next(request)