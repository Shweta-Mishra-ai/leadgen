from __future__ import annotations

from leadgen.models import RawLead
from leadgen.pipeline import score_lead


def make(title, url, source="duckduckgo", snippet=""):
    return RawLead(source=source, title=title, url=url, snippet=snippet)


def test_job_board_aggregator_scores_zero():
    lead = make("AI Automation Freelancer Jobs, Employment",
                "https://www.indeed.com/q-ai-automation-freelancer-jobs.html")
    assert score_lead(lead) == 0


def test_job_board_subdomain_also_blocked():
    lead = make("Genai Engineer Jobs (NOW HIRING)",
                "https://www.ziprecruiter.com/Jobs/Genai-Engineer")
    assert score_lead(lead) == 0


def test_listicle_title_penalized_to_zero():
    lead = make("10 Strategies to Reduce LLM Costs",
                "https://www.example-blog.com/reduce-llm-costs")
    assert score_lead(lead) == 0


def test_best_of_listicle_penalized():
    lead = make("25 Best Freelance AI Workflow Automation Specialists for Hire",
                "https://www.truelancer.com/ai-automation-freelancers")
    assert score_lead(lead) == 0


def test_vendor_tool_site_blocked():
    lead = make("LiteLLM — Open-Source AI Gateway & LLM Proxy", "https://www.litellm.ai/")
    assert score_lead(lead) == 0


def test_genuine_reddit_hiring_post_scores_positive():
    lead = make("Looking for automation and AI freelancers and contractors",
                "https://www.reddit.com/r/n8n/comments/x", source="tavily_reddit")
    assert score_lead(lead) > 0


def test_platform_source_gets_bonus_weight():
    generic = make("Looking for a genai engineer freelancer", "https://example.com/x",
                    source="duckduckgo")
    reddit = make("Looking for a genai engineer freelancer", "https://reddit.com/x",
                   source="tavily_reddit")
    assert score_lead(reddit) > score_lead(generic)


def test_score_never_negative():
    lead = make("Best top 10 guide to how to reduce llm costs strategies",
                "https://example.com/x")
    assert score_lead(lead) == 0  # heavy noise penalty floors at 0, not negative
