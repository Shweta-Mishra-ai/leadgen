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


# Regression tests for a real report run where niche-keyword density beat
# genuine hiring intent: a Reddit career-advice thread and a vendor's own
# "Hire Top X" marketing page both out-scored actual "looking for a
# freelancer... DM me" hiring posts.

def test_generic_career_advice_thread_scores_low_despite_niche_keyword():
    # Matches "data analyst" but is someone asking a question, not hiring.
    lead = RawLead(
        source="tavily_reddit",
        title="How much SQL should a Data Analyst know?",
        url="https://reddit.com/r/dataanalysis/abc",
        snippet="Curious what level of SQL is expected for entry level roles",
    )
    assert score_lead(lead) <= 1


def test_vendor_hire_top_listicle_scores_zero():
    lead = RawLead(
        source="duckduckgo",
        title="Hire Top Web Copywriters | Technical Content Writers",
        url="https://someagency.com/hire",
        snippet="Our agency connects you with vetted copywriters",
    )
    assert score_lead(lead) == 0


def test_freelance_website_roundup_scores_zero():
    lead = RawLead(
        source="tavily_reddit",
        title="Writers Work, Upwork, and other freelance writer websites",
        url="https://reddit.com/r/freelanceWriters/xyz",
        snippet="A list of places to find freelance writing gigs",
    )
    assert score_lead(lead) == 0


def test_genuine_hiring_post_outscores_generic_discussion_and_vendor_noise():
    genuine = score_lead(RawLead(
        source="apify_twitter",
        title="Looking for a freelancer to develop sales and marketing automation",
        url="https://x.com/user/status/1",
        snippet="using n8n and AI workflows for a SMB SaaS solution. DM me if interested.",
    ))
    discussion = score_lead(RawLead(
        source="tavily_reddit",
        title="How much SQL should a Data Analyst know?",
        url="https://reddit.com/r/dataanalysis/abc",
        snippet="Curious what level of SQL is expected for entry level roles",
    ))
    vendor = score_lead(RawLead(
        source="duckduckgo",
        title="Hire Top Web Copywriters | Technical Content Writers",
        url="https://someagency.com/hire",
        snippet="Our agency connects you with vetted copywriters",
    ))
    assert genuine > discussion
    assert genuine > vendor


def test_vendor_devrel_blog_scores_zero():
    # Regression: this exact article scored as a lead, then the email
    # finder guessed a fabricated contact@developer.ibm.com for it and
    # an outreach email actually got sent to that made-up address.
    lead = RawLead(
        source="duckduckgo",
        title="Token optimization: The backbone of effective prompt engineering",
        url="https://developer.ibm.com/articles/awb-token-optimization-backbone-of-effective-prompt-engineering/",
        snippet="Prompt engineering and token optimization are essential for enhancing "
                 "the accuracy, efficiency, and cost-effectiveness of generative AI solutions.",
    )
    assert score_lead(lead) == 0


def test_platform_bonus_requires_hiring_signal():
    no_hiring_signal = RawLead(
        source="tavily_reddit",
        title="What does an entry level data analyst get to do?",
        url="https://reddit.com/r/dataanalysis/def",
        snippet="Just curious about the day to day work",
    )
    with_hiring_signal = RawLead(
        source="tavily_reddit",
        title="Looking for a data analyst, budget ready",
        url="https://reddit.com/r/dataanalysis/ghi",
        snippet="DM me if interested, need someone this week",
    )
    assert score_lead(with_hiring_signal) > score_lead(no_hiring_signal)


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
