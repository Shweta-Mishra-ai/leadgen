from __future__ import annotations

from unittest.mock import MagicMock, patch

from leadgen.sources.apify_source import ApifySource


def test_apify_not_configured_without_both_token_and_cookie():
    assert ApifySource(api_token=None, twitter_cookie=None).is_configured() is False
    assert ApifySource(api_token="tok", twitter_cookie=None).is_configured() is False
    assert ApifySource(api_token=None, twitter_cookie="auth_token=x; ct0=y").is_configured() is False


def test_apify_configured_with_both():
    source = ApifySource(api_token="tok", twitter_cookie="auth_token=x; ct0=y")
    assert source.is_configured() is True


def test_apify_skips_cleanly_when_unconfigured():
    source = ApifySource(api_token=None, twitter_cookie=None)
    assert source.fetch_all(["topic1", "topic2"]) == []


def test_apify_maps_tweet_results():
    source = ApifySource(api_token="tok", twitter_cookie="auth_token=x; ct0=y",
                          max_retries=1, timeout_seconds=5)
    mock_client = MagicMock()
    mock_client.actor.return_value.call.return_value = {"defaultDatasetId": "ds1"}
    mock_client.dataset.return_value.list_items.return_value.items = [
        {"type": "tweet", "url": "https://x.com/i/status/1", "text": "hiring GenAI freelancer",
         "createdAt": "2026-07-01"},
        {"type": "profile", "username": "someone"},  # non-tweet row, should be skipped
    ]
    with patch.object(source, "_get_client", return_value=mock_client):
        results = source.fetch_all(["genai freelancer"])
    assert len(results) == 1
    assert results[0].source == "apify_twitter"


def test_apify_run_failure_returns_empty_not_raises():
    source = ApifySource(api_token="tok", twitter_cookie="auth_token=x; ct0=y",
                          max_retries=1, timeout_seconds=5)
    mock_client = MagicMock()
    mock_client.actor.return_value.call.side_effect = RuntimeError("actor run failed")
    with patch.object(source, "_get_client", return_value=mock_client):
        results = source.fetch_all(["topic"])
    assert results == []


def test_apify_single_run_covers_all_topics():
    """Confirms cost-control design: one actor.call() for ALL topics,
    not one per topic — this is what keeps it inside the free credit."""
    source = ApifySource(api_token="tok", twitter_cookie="auth_token=x; ct0=y",
                          max_retries=1, timeout_seconds=5)
    mock_client = MagicMock()
    mock_client.actor.return_value.call.return_value = {"defaultDatasetId": "ds1"}
    mock_client.dataset.return_value.list_items.return_value.items = []
    with patch.object(source, "_get_client", return_value=mock_client):
        source.fetch_all(["topic1", "topic2", "topic3"])
    assert mock_client.actor.return_value.call.call_count == 1
