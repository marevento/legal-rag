"""HTTP Basic Auth for the legal-rag API."""

from __future__ import annotations

import functools
import logging
import secrets
from typing import Callable

from quart import Response, request

import config

logger = logging.getLogger(__name__)

_auth_warning_logged = False


def require_auth(f: Callable) -> Callable:
    """Decorator to enforce HTTP Basic Auth on a route."""

    @functools.wraps(f)
    async def decorated(*args, **kwargs):
        # CORS preflight requests don't carry auth headers — let them through
        if request.method == "OPTIONS":
            return await f(*args, **kwargs)

        auth = request.authorization

        if not config.AUTH_USERS:
            global _auth_warning_logged
            if not _auth_warning_logged:
                logger.warning(
                    "No users configured — authentication is DISABLED. "
                    "Set AUTH_USERS or AUTH_PASSWORD env var to enable authentication."
                )
                _auth_warning_logged = True
            return await f(*args, **kwargs)

        if auth is None or not _check_credentials(auth.username, auth.password):
            return Response("Authentication required", 401)
        return await f(*args, **kwargs)

    return decorated


def _check_credentials(username: str | None, password: str | None) -> bool:
    """Constant-time comparison of credentials against all configured users."""
    if username is None or password is None:
        return False
    expected_password = config.AUTH_USERS.get(username)
    if expected_password is None:
        # Still do a comparison to avoid timing leaks on username existence
        secrets.compare_digest(password, "dummy")
        return False
    return secrets.compare_digest(password, expected_password)
