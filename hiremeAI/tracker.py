"""SQLite tracker for application logging."""

import sqlite3
from datetime import datetime
from typing import Any

from hiremeAI import config


def get_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database."""
    db_path = config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database schema."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                platform TEXT NOT NULL,
                portal_type TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                fit_score REAL,
                fit_reason TEXT,
                applied_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_applications_status
            ON applications(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_applications_url
            ON applications(url)
        """)
        conn.commit()
    finally:
        conn.close()


def log_application(
    job_id: str,
    company: str,
    title: str,
    url: str,
    platform: str,
    portal_type: str | None = None,
    status: str = "pending",
    fit_score: float | None = None,
    fit_reason: str | None = None,
) -> int:
    """Log a new application attempt. Returns the application ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO applications
            (job_id, company, title, url, platform, portal_type, status, fit_score, fit_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, company, title, url, platform, portal_type, status, fit_score, fit_reason),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_status(
    url: str,
    status: str,
    fit_score: float | None = None,
    fit_reason: str | None = None,
) -> None:
    """Update application status after filter or submission."""
    conn = get_connection()
    try:
        applied_at = datetime.now().isoformat() if status == "submitted" else None
        conn.execute(
            """
            UPDATE applications
            SET status = ?,
                fit_score = COALESCE(?, fit_score),
                fit_reason = ?,
                applied_at = COALESCE(?, applied_at),
                updated_at = datetime('now')
            WHERE url = ?
            """,
            (status, fit_score, fit_reason, applied_at, url),
        )
        conn.commit()
    finally:
        conn.close()


def get_applications(status: str | None = None) -> list[dict[str, Any]]:
    """Get all applications, optionally filtered by status."""
    conn = get_connection()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM applications WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM applications ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_application_by_url(url: str) -> dict[str, Any] | None:
    """Get application by URL."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM applications WHERE url = ?",
            (url,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def is_url_applied(url: str) -> bool:
    """Check if a URL has already been applied to."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status FROM applications WHERE url = ?",
            (url,),
        ).fetchone()
        return row is not None and row["status"] in ("submitted", "manual_review")
    finally:
        conn.close()


# Initialize database on module import
init_db()
