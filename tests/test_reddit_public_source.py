from __future__ import annotations

from unittest.mock import MagicMock, patch

from leadgen.sources.reddit_public_source import RedditPublicSource

NICHE_KEYWORDS = ["genai engineer", "llm cost optimization"]


def test_always_configured_no_key_needed():
    source = RedditPublicSource(niche_keywords=NICHE_KEYWORDS)
    assert source.is_configured() is True


def fake_response(posts):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": {"children": [{"data": p} for p in posts]}}
    resp.raise_for_status = MagicMock()
    return resp


def test_filters_by_niche_keywords():
    source = RedditPublicSource(niche_keywords=NICHE_KEYWORDS, max_retries=1, timeout_seconds=5)
    posts = [
        {"title": "Need a genai engineer for our startup", "selftext": "budget ready",
         "permalink": "/r/forhire/comments/1/"},
        {"title": "My cat is cute", "selftext": "", "permalink": "/r/forhire/comments/2/"},
    ]
    with patch("requests.get", return_value=fake_response(posts)):
        results = source.fetch_all([])
    # only relevant post should pass the keyword filter, across all 8 subreddits scanned
    assert all("genai" in r.title.lower() for r in results)
    assert len(results) >= 1


def test_rate_limit_raises_retryable_and_recovers():
    source = RedditPublicSource(niche_keywords=NICHE_KEYWORDS, max_retries=2, timeout_seconds=5)
    rate_limited = MagicMock(status_code=429)
    ok = fake_response([])
    with patch("requests.get", side_effect=[rate_limited, ok] * 8):
        results = source.fetch_all([])
    assert results == []  # no matching posts, but no crash either


def test_circuit_breaker_on_repeated_failures():
    source = RedditPublicSource(niche_keywords=NICHE_KEYWORDS, max_retries=1, timeout_seconds=5)
    with patch("requests.get", side_effect=ConnectionError("down")):
        results = source.fetch_all([])
    assert results == []
