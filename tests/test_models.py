from __future__ import annotations

import pytest
from pydantic import ValidationError

from leadgen.models import RawLead, ScoredLead


def test_raw_lead_requires_url():
    with pytest.raises(ValidationError):
        RawLead(source="test", title="x", url="", snippet="y")


def test_raw_lead_rejects_malformed_url():
    with pytest.raises(ValidationError):
        RawLead(source="test", title="x", url="not-a-url", snippet="y")


def test_raw_lead_accepts_valid_data():
    lead = RawLead(source="grok_x", title="Need help", url="https://x.com/foo", snippet="hi")
    assert lead.source == "grok_x"


def test_raw_lead_coerces_none_fields_to_empty_string():
    lead = RawLead(source="test", title=None, url="https://example.com", snippet=None)
    assert lead.title == ""
    assert lead.snippet == ""


def test_scored_lead_truncates_long_fields():
    raw = RawLead(
        source="test",
        title="x" * 500,
        url="https://example.com",
        snippet="y" * 500,
    )
    scored = ScoredLead.from_raw(raw, score=5)
    assert len(scored.title) <= 200
    assert len(scored.snippet) <= 300


def test_scored_lead_rejects_negative_score():
    raw = RawLead(source="test", title="x", url="https://example.com", snippet="y")
    with pytest.raises(ValidationError):
        ScoredLead.from_raw(raw, score=-1)
