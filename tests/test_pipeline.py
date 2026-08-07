from __future__ import annotations

from unittest.mock import MagicMock, patch

from leadgen.config import Settings
from leadgen.models import RawLead
from leadgen.pipeline import run_pipeline, score_lead


def test_score_lead_rewards_niche_and_hiring_signal():
    lead = RawLead(
        source="test",
        title="Looking for a GenAI engineer to cut our LLM cost",
        url="https://example.com/1",
        snippet="hiring freelancer with budget ready",
    )
    score = score_lead(lead)
    assert score > 0


def test_score_lead_zero_for_irrelevant_text():
    lead = RawLead(
        source="test", title="My cat is cute", url="https://example.com/2",
        snippet="just a random post about pets",
    )
    assert score_lead(lead) == 0


def test_pipeline_survives_one_source_raising(temp_store):
    settings = Settings(_env_file=None, XAI_API_KEY="fake")

    def fake_build_sources(_settings):
        good = MagicMock()
        good.name = "good"
        good.fetch_all.return_value = [
            RawLead(source="good", title="hiring genai freelancer budget",
                     url="https://example.com/good", snippet="need help")
        ]
        bad = MagicMock()
        bad.name = "bad"
        bad.fetch_all.side_effect = RuntimeError("source exploded")
        return [good, bad]

    with patch("leadgen.pipeline.build_sources", side_effect=fake_build_sources):
        summary = run_pipeline(settings, temp_store)

    assert summary["new_leads"] == 1
    assert temp_store.count() == 1


def test_pipeline_writes_only_relevant_leads(temp_store):
    settings = Settings(_env_file=None)

    def fake_build_sources(_settings):
        src = MagicMock()
        src.name = "src"
        src.fetch_all.return_value = [
            RawLead(source="src", title="hiring genai freelancer", url="https://example.com/relevant",
                     snippet="budget ready"),
            RawLead(source="src", title="unrelated cat post", url="https://example.com/irrelevant",
                     snippet="nothing to do with anything"),
        ]
        return [src]

    with patch("leadgen.pipeline.build_sources", side_effect=fake_build_sources):
        run_pipeline(settings, temp_store)

    urls = [row["url"] for row in temp_store.all_leads()]
    assert "https://example.com/relevant" in urls
    assert "https://example.com/irrelevant" not in urls
