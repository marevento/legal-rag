"""Usage tracking via SQLite for analytics and audit."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import config

logger = logging.getLogger(__name__)

_DB_PATH: Path | None = None


def init_db(data_dir: str | None = None) -> None:
    """Initialize the usage database."""
    global _DB_PATH
    _DB_PATH = Path(data_dir or config.PERSIST_DIR) / "usage.db"
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                user_email TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                query TEXT,
                search_strategy TEXT,
                confidence TEXT,
                citation_count INTEGER,
                latency_ms REAL,
                metadata_json TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_log(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_email ON usage_log(user_email)
        """)
    logger.info("Usage database initialized at %s", _DB_PATH)


@contextmanager
def _get_conn() -> Iterator[sqlite3.Connection]:
    """Get a SQLite connection (short-lived, per-operation)."""
    db_uri = f"file:{_DB_PATH}?nolock=1"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=OFF")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_request(
    user_email: str,
    endpoint: str,
    method: str,
    query: str | None = None,
    search_strategy: str | None = None,
    confidence: str | None = None,
    citation_count: int | None = None,
    latency_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log a request to the usage database."""
    if _DB_PATH is None:
        return
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO usage_log
                   (timestamp, user_email, endpoint, method, query,
                    search_strategy, confidence, citation_count, latency_ms, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    time.time(),
                    user_email,
                    endpoint,
                    method,
                    query,
                    search_strategy,
                    confidence,
                    citation_count,
                    latency_ms,
                    json.dumps(metadata) if metadata else None,
                ),
            )
    except Exception as e:
        logger.error("Failed to log usage to %s: %s", _DB_PATH, e)


def get_daily_chat_count() -> int:
    """Return the number of chat queries today (UTC)."""
    if _DB_PATH is None:
        return 0
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM usage_log WHERE endpoint = '/chat' "
                "AND date(timestamp, 'unixepoch') = date('now')"
            ).fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


def get_usage_stats() -> dict[str, Any]:
    """Get aggregated usage statistics for the admin dashboard."""
    if _DB_PATH is None:
        return {"error": "Usage tracking not initialized"}

    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM usage_log").fetchone()[0]

        # Chat queries only
        chat_total = conn.execute(
            "SELECT COUNT(*) FROM usage_log WHERE endpoint = '/chat'"
        ).fetchone()[0]

        # Per-user breakdown
        users = conn.execute("""
            SELECT user_email, COUNT(*) as count,
                   MIN(timestamp) as first_seen, MAX(timestamp) as last_seen
            FROM usage_log
            GROUP BY user_email
            ORDER BY count DESC
        """).fetchall()

        # Queries per day (last 30 days)
        daily = conn.execute("""
            SELECT date(timestamp, 'unixepoch') as day, COUNT(*) as count
            FROM usage_log
            WHERE timestamp > ? AND endpoint = '/chat'
            GROUP BY day ORDER BY day
        """, (time.time() - 30 * 86400,)).fetchall()

        # Strategy distribution (chat queries only)
        strategies = conn.execute("""
            SELECT search_strategy, COUNT(*) as count
            FROM usage_log
            WHERE endpoint = '/chat' AND search_strategy IS NOT NULL
            GROUP BY search_strategy
        """).fetchall()

        # Confidence distribution
        confidence = conn.execute("""
            SELECT confidence, COUNT(*) as count
            FROM usage_log
            WHERE endpoint = '/chat' AND confidence IS NOT NULL
            GROUP BY confidence
        """).fetchall()

        # Average latency
        avg_latency = conn.execute("""
            SELECT AVG(latency_ms) FROM usage_log
            WHERE endpoint = '/chat' AND latency_ms IS NOT NULL
        """).fetchone()[0]

        # Recent queries (last 50)
        recent = conn.execute("""
            SELECT timestamp, user_email, query, search_strategy,
                   confidence, citation_count, latency_ms
            FROM usage_log
            WHERE endpoint = '/chat' AND query IS NOT NULL
            ORDER BY timestamp DESC LIMIT 50
        """).fetchall()

        return {
            "total_requests": total,
            "total_chat_queries": chat_total,
            "users": [
                {
                    "email": r["user_email"],
                    "count": r["count"],
                    "first_seen": r["first_seen"],
                    "last_seen": r["last_seen"],
                }
                for r in users
            ],
            "daily_queries": [
                {"day": r["day"], "count": r["count"]} for r in daily
            ],
            "strategy_distribution": [
                {"strategy": r["search_strategy"], "count": r["count"]}
                for r in strategies
            ],
            "confidence_distribution": [
                {"confidence": r["confidence"], "count": r["count"]}
                for r in confidence
            ],
            "avg_latency_ms": round(avg_latency, 1) if avg_latency else None,
            "recent_queries": [
                {
                    "timestamp": r["timestamp"],
                    "user_email": r["user_email"],
                    "query": r["query"],
                    "search_strategy": r["search_strategy"],
                    "confidence": r["confidence"],
                    "citation_count": r["citation_count"],
                    "latency_ms": round(r["latency_ms"], 1) if r["latency_ms"] else None,
                }
                for r in recent
            ],
        }
