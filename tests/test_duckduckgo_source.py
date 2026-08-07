from __future__ import annotations

from unittest.mock import patch

from leadgen.sources.duckduckgo_source import DuckDuckGoSource


def test_duckduckgo_always_configured():
    source = DuckDuckGoSource()
    assert source.is_configured() is True


def test_duckduckgo_fetches_and_maps_results():
    source = DuckDuckGoSource(max_retries=1, timeout_seconds=5)
    mock_hits = [
        {"title": "Need help reducing LLM API cost", "href": "https://example.com/ddg1", "body": "Looking for freelancer"}
    ]

    def mock_fetch(topic):
        return [
            {
                "source": "duckduckgo",
                "title": h.get("title", ""),
                "url": h.get("href", ""),
                "snippet": h.get("body", "")[:300],
                "created": "",
            }
            for h in mock_hits
        ]

    with patch.object(source, "_fetch_topic", side_effect=mock_fetch):
        results = source.fetch_all(["reduce llm cost"])

    assert len(results) >= 1
    assert results[0].source == "duckduckgo"
    assert str(results[0].url) == "https://example.com/ddg1"
