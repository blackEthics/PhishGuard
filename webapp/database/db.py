"""db.py — SQLite scan history for PhishGuard."""

import json
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

# Allow overriding the DB path via environment variable for testing / deployment.
_default_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "phishguard.db")
DB_PATH: str = os.environ.get("PHISHGUARD_DB_PATH", _default_db_path)


def _get_conn() -> sqlite3.Connection:
    """Open a WAL-mode connection to the database."""
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def _extract_tld(url: str) -> str:
    """Extract the TLD (e.g. '.com') from a URL, or '' if unparseable."""
    try:
        host = url.split("//")[-1].split("/")[0]
        parts = host.split(".")
        return ("." + parts[-1].lower()) if len(parts) >= 2 else ""
    except Exception:
        return ""


def init_db() -> None:
    """Create the scans table and indexes if they do not exist."""
    con = _get_conn()
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                url        TEXT    NOT NULL,
                verdict    TEXT    NOT NULL,
                confidence REAL,
                tld        TEXT    DEFAULT '',
                timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP,
                results    TEXT
            )
        """)
        # Migration: add tld column to databases created before this column existed.
        try:
            con.execute("ALTER TABLE scans ADD COLUMN tld TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # Column already exists — normal on repeated startups
        con.execute("CREATE INDEX IF NOT EXISTS idx_scans_timestamp ON scans(timestamp)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_scans_tld ON scans(tld)")
        con.commit()
    finally:
        con.close()


def save_scan(url: str, verdict: str, confidence: float, results: dict) -> None:
    """Insert one scan record into the database."""
    con = _get_conn()
    try:
        con.execute(
            "INSERT INTO scans (url, verdict, confidence, tld, results) VALUES (?, ?, ?, ?, ?)",
            (url, verdict, confidence, _extract_tld(url), json.dumps(results)),
        )
        con.commit()
    finally:
        con.close()


def save_scans_batch(scans: list[tuple]) -> None:
    """Insert multiple scan records in a single transaction.

    Args:
        scans: List of (url, verdict, confidence, results_json_str) tuples.
    """
    con = _get_conn()
    try:
        con.executemany(
            "INSERT INTO scans (url, verdict, confidence, tld, results) VALUES (?, ?, ?, ?, ?)",
            [
                (url, verdict, confidence, _extract_tld(url), results_json)
                for url, verdict, confidence, results_json in scans
            ],
        )
        con.commit()
    finally:
        con.close()


def get_dashboard_stats() -> dict:
    """Return all stats needed by the analytics dashboard."""
    con = _get_conn()
    try:
        total    = con.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        phishing = con.execute("SELECT COUNT(*) FROM scans WHERE verdict = 'bad'").fetchone()[0]
        today    = con.execute(
            "SELECT COUNT(*) FROM scans WHERE date(timestamp) = date('now')"
        ).fetchone()[0]
        this_week = con.execute(
            "SELECT COUNT(*) FROM scans WHERE timestamp >= datetime('now', '-7 days')"
        ).fetchone()[0]

        daily_rows = con.execute("""
            SELECT date(timestamp)                                   AS day,
                   COUNT(*)                                          AS total,
                   SUM(CASE WHEN verdict = 'bad' THEN 1 ELSE 0 END) AS phishing
            FROM   scans
            WHERE  timestamp >= datetime('now', '-7 days')
            GROUP  BY day
            ORDER  BY day
        """).fetchall()

        # TLD aggregation via SQL — avoids loading all URLs into Python memory.
        tld_rows = con.execute("""
            SELECT tld, COUNT(*) AS cnt
            FROM   scans
            WHERE  tld != ''
            GROUP  BY tld
            ORDER  BY cnt DESC
            LIMIT  8
        """).fetchall()
    finally:
        con.close()

    return {
        "total":        total,
        "phishing":     phishing,
        "safe":         total - phishing,
        "phishing_pct": round(phishing / total * 100, 1) if total else 0,
        "today":        today,
        "this_week":    this_week,
        "daily_counts": [
            {"date": r[0], "total": r[1], "phishing": r[2]}
            for r in daily_rows
        ],
        "top_tlds": [
            {"tld": r[0], "count": r[1]} for r in tld_rows
        ],
    }


def get_recent_history(limit: int = 20) -> list[dict]:
    """Return a list of dicts for the history table."""
    con = _get_conn()
    try:
        rows = con.execute(
            "SELECT id, url, verdict, confidence, timestamp FROM scans "
            "ORDER BY timestamp DESC LIMIT ?",
            (limit,),
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
