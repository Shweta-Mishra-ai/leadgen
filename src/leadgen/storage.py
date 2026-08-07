"""Persistence layer. SQLite instead of flat CSV+seen_ids.txt:
- UNIQUE constraint on url_hash gives atomic, race-safe dedup (no
  read-modify-write on a text file)
- indexed queries for "top N by score" instead of loading everything
  into memory and sorting in Python
- a single transaction per pipeline run — either all new leads land
  or none do, no partial-write corruption if the process dies mid-run
"""

from __future__ import annotations

import csv
import hashlib
import os
import sqlite3
from contextlib import contextmanager

from leadgen.models import ScoredLead

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    snippet TEXT NOT NULL,
    score INTEGER NOT NULL,
    created TEXT,
    found_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_found_at ON leads(found_at DESC);

CREATE TABLE IF NOT EXISTS outreach_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_url TEXT NOT NULL,
    recipient_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    status TEXT NOT NULL,
    followup_stage INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_outreach_sent_at ON outreach_logs(sent_at DESC);

-- Small key/value scratch space that has to outlive a single process.
-- Currently holds the Telegram getUpdates offset: the bot runs as a
-- short-lived cron job, so without persisting the offset every run would
-- re-process the same 24h of commands Telegram still has queued.
CREATE TABLE IF NOT EXISTS bot_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


class LeadStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # Auto-create parent directory if it doesn't exist (e.g. /data on Render.com)
        parent = os.path.dirname(os.path.abspath(db_path))
        os.makedirs(parent, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def insert_new(self, leads: list[ScoredLead]) -> int:
        """Insert leads, skipping any whose URL was already seen.
        Returns count of genuinely new rows inserted."""
        inserted = 0
        with self._connect() as conn:
            for lead in leads:
                try:
                    conn.execute(
                        """INSERT INTO leads
                           (url_hash, source, title, url, snippet, score, created, found_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            url_hash(lead.url), lead.source, lead.title, lead.url,
                            lead.snippet, lead.score, lead.created, lead.found_at,
                        ),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    continue  # already seen, expected & fine
        return inserted

    def top_leads(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM leads ORDER BY score DESC, found_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def all_leads(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM leads ORDER BY score DESC, found_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def leads_found_on(self, day: str) -> list[dict]:
        """Leads first seen on a given UTC day ('YYYY-MM-DD').

        found_at is an ISO timestamp, so a prefix match on the date is
        enough and still uses the found_at index.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM leads WHERE found_at LIKE ? ORDER BY score DESC, found_at DESC",
                (f"{day}%",),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_state(self, key: str, default: str | None = None) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM bot_state WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO bot_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )

    def get_lead_by_id(self, lead_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
            return dict(row) if row else None

    def log_outreach(
        self,
        lead_url: str,
        recipient_email: str,
        subject: str,
        body: str,
        status: str = "sent",
        followup_stage: int = 0,
    ) -> None:
        from datetime import UTC, datetime
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO outreach_logs
                   (lead_url, recipient_email, subject, body, sent_at, status, followup_stage)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (lead_url, recipient_email, subject, body, now, status, followup_stage),
            )
            conn.commit()

    def get_pending_followups(self, days_since: int, stage: int) -> list[dict]:
        """Return outreach logs eligible for a specific follow-up stage.

        A lead is eligible when:
        - Its last outreach status is 'sent' (not replied/unsubscribed)
        - Its current followup_stage == stage - 1
        - It was last sent >= days_since days ago
        """
        from datetime import UTC, datetime, timedelta
        cutoff = (datetime.now(UTC) - timedelta(days=days_since)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ol.*
                FROM outreach_logs ol
                INNER JOIN (
                    SELECT lead_url, MAX(sent_at) AS last_sent
                    FROM outreach_logs
                    GROUP BY lead_url
                ) latest ON ol.lead_url = latest.lead_url AND ol.sent_at = latest.last_sent
                WHERE ol.status = 'sent'
                  AND ol.followup_stage = ?
                  AND ol.sent_at <= ?
                """,
                (stage - 1, cutoff),
            ).fetchall()
            return [dict(r) for r in rows]

    def all_outreach_logs(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM outreach_logs ORDER BY sent_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def export_csv(self, path: str) -> None:
        leads = self.all_leads()
        fieldnames = ["source", "title", "url", "snippet", "score", "created", "found_at"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for lead in leads:
                writer.writerow({k: lead[k] for k in fieldnames})

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
