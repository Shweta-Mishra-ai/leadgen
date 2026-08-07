"""Data models with validation at the boundary.

Every source returns raw dicts; RawLead.model_validate() is the single
gate everything passes through before entering the pipeline. Bad data
(missing URL, garbage score) is rejected here, not three files downstream.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator


class RawLead(BaseModel):
    """What a source hands back, before scoring/dedup."""

    source: str
    title: str = ""
    url: HttpUrl
    snippet: str = ""
    created: str = ""  # ISO string or empty; sources don't always know

    @field_validator("title", "snippet", mode="before")
    @classmethod
    def coerce_none_to_empty(cls, v: object) -> str:
        return "" if v is None else str(v)


class ScoredLead(BaseModel):
    """A lead after scoring — this is what gets persisted."""

    source: str
    title: str = Field(max_length=200)
    url: str
    snippet: str = Field(max_length=300)
    score: int = Field(ge=0)
    created: str = ""
    found_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @classmethod
    def from_raw(cls, raw: RawLead, score: int) -> ScoredLead:
        return cls(
            source=raw.source,
            title=raw.title[:200],
            url=str(raw.url),
            snippet=raw.snippet[:300],
            score=score,
            created=raw.created,
        )
