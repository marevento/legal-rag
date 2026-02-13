"""Magic-link authentication routes."""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import time
from dataclasses import dataclass, field

from quart import Blueprint, g, jsonify, request
from quart.typing import ResponseReturnValue

import config
from core.authentication import create_jwt, require_auth

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class _PendingAuth:
    code: str
    token: str
    expires_at: float
    attempts: int = 0


# In-memory stores (single-instance deployment)
_pending_auths: dict[str, _PendingAuth] = {}
_rate_limits: dict[str, list[float]] = {}

RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 3600  # 1 hour
CODE_TTL = 600  # 10 minutes
MAX_CODE_ATTEMPTS = 5


def _check_rate_limit(ip: str) -> bool:
    """Return True if the IP is within rate limits."""
    now = time.time()
    timestamps = _rate_limits.get(ip, [])
    timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    _rate_limits[ip] = timestamps
    return len(timestamps) < RATE_LIMIT_MAX


def _record_rate_limit(ip: str) -> None:
    _rate_limits.setdefault(ip, []).append(time.time())


async def _send_email(to_email: str, code: str, magic_link: str) -> None:
    """Send magic link email via Azure Communication Services."""
    if not config.AZURE_COMMUNICATION_CONNECTION_STRING:
        logger.warning("ACS not configured — email not sent to %s (set AZURE_COMMUNICATION_CONNECTION_STRING)", to_email)
        if not config.JWT_SECRET:
            logger.info("Dev mode — code for %s: %s", to_email, code)
        return

    def _send() -> None:
        from azure.communication.email import EmailClient

        client = EmailClient.from_connection_string(config.AZURE_COMMUNICATION_CONNECTION_STRING)
        message = {
            "senderAddress": config.ACS_SENDER_ADDRESS,
            "content": {
                "subject": "Your access code for Mietrecht Assistent",
                "plainText": f"Your code: {code}\n\nOr click: {magic_link}\n\nThis code expires in 10 minutes.",
                "html": (
                    f"<h2>Mietrecht Assistent</h2>"
                    f"<p>Your access code: <strong style='font-size:24px;letter-spacing:4px'>{code}</strong></p>"
                    f"<p>Or <a href='{magic_link}'>click here to access the app</a>.</p>"
                    f"<p><small>This code expires in 10 minutes.</small></p>"
                ),
            },
            "recipients": {"to": [{"address": to_email}]},
        }
        poller = client.begin_send(message)
        poller.result()

    await asyncio.to_thread(_send)


@auth_bp.before_app_serving
async def _start_cleanup_task() -> None:
    """Periodically clean up expired pending auths and stale rate limit entries."""

    async def _cleanup() -> None:
        while True:
            await asyncio.sleep(60)
            now = time.time()
            expired = [k for k, v in _pending_auths.items() if v.expires_at < now]
            for k in expired:
                del _pending_auths[k]
            stale = [k for k, v in _rate_limits.items() if all(now - t > RATE_LIMIT_WINDOW for t in v)]
            for k in stale:
                del _rate_limits[k]

    asyncio.create_task(_cleanup())


@auth_bp.route("/request-access", methods=["POST"])
async def request_access() -> ResponseReturnValue:
    """Send a magic link and code to the provided email."""
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "unknown"
    if not _check_rate_limit(ip):
        return jsonify({"error": "Too many requests. Try again later."}), 429

    data = await request.get_json()
    email = (data.get("email") or "").strip().lower()
    if not email or not EMAIL_RE.match(email):
        return jsonify({"error": "Valid email address required"}), 400

    _record_rate_limit(ip)

    code = str(secrets.randbelow(900000) + 100000)
    token = secrets.token_urlsafe(32)

    _pending_auths[email] = _PendingAuth(
        code=code,
        token=token,
        expires_at=time.time() + CODE_TTL,
    )

    magic_link = f"{config.APP_URL}/auth/verify?token={token}&email={email}"

    try:
        await _send_email(email, code, magic_link)
    except Exception:
        logger.exception("Failed to send email to %s", email)
        return jsonify({"error": "Failed to send email. Please try again."}), 500

    return jsonify({"status": "sent"})


@auth_bp.route("/verify", methods=["POST"])
async def verify() -> ResponseReturnValue:
    """Verify a magic link token or 6-digit code."""
    data = await request.get_json()
    email = (data.get("email") or "").strip().lower()
    code = data.get("code")
    token = data.get("token")

    if not email:
        return jsonify({"error": "Email required"}), 400

    pending = _pending_auths.get(email)
    if not pending or pending.expires_at < time.time():
        _pending_auths.pop(email, None)
        return jsonify({"error": "Code expired or not found. Please request a new one."}), 401

    if token:
        if not secrets.compare_digest(pending.token, token):
            return jsonify({"error": "Invalid link"}), 401
    elif code:
        pending.attempts += 1
        if pending.attempts >= MAX_CODE_ATTEMPTS:
            del _pending_auths[email]
            return jsonify({"error": "Too many attempts. Please request a new code."}), 429
        if not secrets.compare_digest(pending.code, code):
            return jsonify({"error": "Invalid code"}), 401
    else:
        return jsonify({"error": "Code or token required"}), 400

    del _pending_auths[email]
    jwt_token = create_jwt(email)
    role = "admin" if email in config.ADMIN_EMAILS else "viewer"

    return jsonify({"token": jwt_token, "role": role})


@auth_bp.route("/me", methods=["GET"])
@require_auth
async def me() -> ResponseReturnValue:
    """Return the current user's email and role."""
    return jsonify({"email": g.user_email, "role": g.user_role})
