from __future__ import annotations

from unittest.mock import MagicMock, patch

from leadgen.sources.gemini import GeminiSource


def test_gemini_not_configured_without_key():
    source = GeminiSource(api_key=None)
    assert source.is_configured() is False
    assert source.fetch_all(["topic"]) == []


def test_gemini_configured_with_key():
    source = GeminiSource(api_key="gemini-key")
    assert source.is_configured() is True


def test_gemini_fetches_and_parses_json_response():
    source = GeminiSource(api_key="gemini-key", model="gemini-2.5-flash", max_retries=1, timeout_seconds=5)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": '```json\n[{"title": "Hiring GenAI Dev", "url": "https://example.com/1", "snippet": "Need help reducing LLM costs"}]\n```'
                        }
                    ]
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as mock_post:
        results = source.fetch_all(["reduce llm cost"])

    assert len(results) == 1
    assert results[0].source == "gemini"
    assert str(results[0].url) == "https://example.com/1"
    assert "gemini-2.5-flash" in mock_post.call_args[0][0]


def test_gemini_handles_non_json_response_gracefully():
    source = GeminiSource(api_key="gemini-key", max_retries=1, timeout_seconds=5)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "I could not find any leads."}]}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp):
        results = source.fetch_all(["topic"])

    assert results == []
