from __future__ import annotations

from unittest.mock import MagicMock, patch

from leadgen.sources.tavily_source import TavilySource


def test_tavily_not_configured_without_key():
    source = TavilySource(api_key=None)
    assert source.is_configured() is False
    assert source.fetch_all(["topic"]) == []


def test_tavily_configured_with_key():
    source = TavilySource(api_key="tvly-test")
    assert source.is_configured() is True


def test_tavily_maps_results_from_both_web_and_reddit_passes():
    source = TavilySource(api_key="tvly-test", max_retries=1, timeout_seconds=5)

    mock_client = MagicMock()
    mock_client.search.side_effect = [
        {"results": [{"title": "Web result", "url": "https://example.com/1",
                      "content": "hiring for GenAI work", "published_date": "2026-07-01"}]},
        {"results": [{"title": "Reddit result", "url": "https://reddit.com/r/x/1",
                      "content": "need automation help", "published_date": ""}]},
    ]
    with patch.object(source, "_get_client", return_value=mock_client):
        results = source.fetch_all(["genai freelancer"])

    sources_seen = {r.source for r in results}
    assert "tavily_web" in sources_seen
    assert "tavily_reddit" in sources_seen
    assert len(results) == 2


def test_tavily_drops_rows_with_empty_url():
    source = TavilySource(api_key="tvly-test", max_retries=1, timeout_seconds=5)
    mock_client = MagicMock()
    mock_client.search.side_effect = [
        {"results": [{"title": "No URL", "url": "", "content": "x"}]},
        {"results": []},
    ]
    with patch.object(source, "_get_client", return_value=mock_client):
        results = source.fetch_all(["topic"])
    assert results == []
