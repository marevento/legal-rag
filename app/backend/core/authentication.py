"""JWT-based authentication for the legal-rag API."""

from __future__ import annotations

import functools
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

import jwt
from quart import Response, g, request

import config

logger = logging.getLogger(__name__)

_auth_warning_logged = False


def create_jwt(email: str) -> str:
    """Create a signed JWT for an authenticated user."""
    role = "admin" if email.lower() in config.ADMIN_EMAILS else "viewer"
    payload = {
        "sub": email.lower(),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def require_auth(f: Callable) -> Callable:
    """Decorator to enforce JWT Bearer auth on a route."""

    @functools.wraps(f)
    async def decorated(*args, **kwargs):
        if request.method == "OPTIONS":
            return await f(*args, **kwargs)

        if not config.JWT_SECRET:
            if config.AZURE_COMMUNICATION_CONNECTION_STRING:
                return Response("Server misconfiguration: JWT_SECRET not set", 500)
            global _auth_warning_logged
            if not _auth_warning_logged:
                logger.warning(
                    "JWT_SECRET not set — authentication is DISABLED (dev mode). "
                    "Set JWT_SECRET env var to enable authentication."
                )
                _auth_warning_logged = True
            g.user_email = "dev@localhost"
            g.user_role = "viewer"
            return await f(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response("Authentication required", 401)

        token = auth_header[7:]
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return Response("Token expired", 401)
        except jwt.InvalidTokenError:
            return Response("Invalid token", 401)

        g.user_email = payload["sub"]
        g.user_role = payload["role"]
        return await f(*args, **kwargs)

    return decorated


def require_role(role: str) -> Callable:
    """Decorator factory to enforce a specific role (use after @require_auth)."""

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        async def decorated(*args, **kwargs):
            if getattr(g, "user_role", None) != role:
                return Response("Forbidden", 403)
            return await f(*args, **kwargs)

        return decorated

    return decorator
