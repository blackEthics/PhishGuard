"""database/users.py — User and session management for PhishGuard auth."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from database.db import _get_conn

logger = logging.getLogger(__name__)


def init_user_tables() -> None:
    """Create auth tables and migrate existing scans table with user_id column."""
    con = _get_conn()
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER  PRIMARY KEY AUTOINCREMENT,
                google_id   TEXT     UNIQUE NOT NULL,
                email       TEXT     UNIQUE NOT NULL,
                name        TEXT     NOT NULL,
                picture     TEXT     DEFAULT '',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login  DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active   INTEGER  DEFAULT 1
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email)")

        con.execute("""
            CREATE TABLE IF NOT EXISTS login_sessions (
                id            INTEGER  PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER  NOT NULL REFERENCES users(id),
                session_token TEXT     UNIQUE NOT NULL,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at    DATETIME NOT NULL,
                ip_address    TEXT,
                user_agent    TEXT,
                is_active     INTEGER  DEFAULT 1
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON login_sessions(user_id)")

        # Migrate scans table: add user_id FK if missing (safe on repeated startup)
        try:
            con.execute("ALTER TABLE scans ADD COLUMN user_id INTEGER REFERENCES users(id)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_scans_user_id ON scans(user_id)")
            logger.info("Migrated scans table: added user_id column")
        except sqlite3.OperationalError:
            pass  # Column already exists — normal on repeated startups

        con.commit()
        logger.info("Auth tables ready")
    finally:
        con.close()


def upsert_user(google_id: str, email: str, name: str, picture: str) -> dict:
    """Insert or update a user keyed on google_id. Returns the current row."""
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    con = _get_conn()
    try:
        con.execute(
            """
            INSERT INTO users (google_id, email, name, picture, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(google_id) DO UPDATE SET
                email      = excluded.email,
                name       = excluded.name,
                picture    = excluded.picture,
                last_login = ?
            """,
            (google_id, email, name, picture, now, now, now),
        )
        con.commit()
        return get_user_by_google_id(google_id)  # type: ignore[return-value]
    finally:
        con.close()


def get_user_by_id(user_id: int) -> dict | None:
    con = _get_conn()
    try:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def get_user_by_google_id(google_id: str) -> dict | None:
    con = _get_conn()
    try:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM users WHERE google_id = ?", (google_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def get_user_scans(user_id: int, limit: int = 50) -> list[dict]:
    """Return scans attributed to this user, newest first."""
    con = _get_conn()
    try:
        rows = con.execute(
            "SELECT id, url, verdict, confidence, timestamp FROM scans "
            "WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        con.close()
    return [
        {
            "id":         r[0],
            "url":        r[1],
            "verdict":    r[2],
            "confidence": r[3],
            "timestamp":  r[4],
        }
        for r in rows
    ]


def get_user_scan_count(user_id: int) -> int:
    con = _get_conn()
    try:
        return con.execute(
            "SELECT COUNT(*) FROM scans WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    finally:
        con.close()


def delete_user(user_id: int) -> None:
    """Soft-delete: mark user and their sessions as inactive."""
    con = _get_conn()
    try:
        con.execute("UPDATE users         SET is_active = 0 WHERE id      = ?", (user_id,))
        con.execute("UPDATE login_sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
        con.commit()
        logger.info("Soft-deleted user id=%s", user_id)
    finally:
        con.close()
