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
        auth = request.authorization

        if not config.AUTH_PASSWORD:
            global _auth_warning_logged
            if not _auth_warning_logged:
                logger.warning(
                    "AUTH_PASSWORD is not set — authentication is DISABLED. "
                    "Set AUTH_PASSWORD env var to enable authentication."
                )
                _auth_warning_logged = True
            return await f(*args, **kwargs)

        if auth is None or not _check_credentials(auth.username, auth.password):
            return Response(
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="legal-rag"'},
            )
        return await f(*args, **kwargs)

    return decorated


def _check_credentials(username: str | None, password: str | None) -> bool:
    """Constant-time comparison of credentials."""
    if username is None or password is None:
        return False
    username_ok = secrets.compare_digest(username, config.AUTH_USERNAME)
    password_ok = secrets.compare_digest(password, config.AUTH_PASSWORD)
    return username_ok and password_ok
