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
"""


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


class LeadStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
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
