from __future__ import annotations

from unittest.mock import MagicMock, patch

from leadgen.sources.grok import GrokSource


def test_grok_not_configured_without_key():
    source = GrokSource(api_key=None)
    assert source.is_configured() is False
    assert source.fetch_all(["topic"]) == []


def test_grok_configured_with_key():
    source = GrokSource(api_key="xai-key")
    assert source.is_configured() is True


def test_grok_fetches_and_parses_json_response():
    source = GrokSource(api_key="xai-key", model="grok-2-latest", max_retries=1, timeout_seconds=5)
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '```json\n[{"platform": "x", "title": "Need LLM dev", "url": "https://x.com/post/1", "snippet": "help"}]\n```'
    )
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    with patch.object(source, "_get_client", return_value=mock_client):
        results = source.fetch_all(["genai engineer"])

    assert len(results) == 1
    assert results[0].source == "grok_x"
    assert str(results[0].url) == "https://x.com/post/1"
    assert mock_client.chat.completions.create.call_args[1]["model"] == "grok-2-latest"


def test_grok_handles_invalid_json():
    source = GrokSource(api_key="xai-key", max_retries=1, timeout_seconds=5)
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Invalid text response"
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    with patch.object(source, "_get_client", return_value=mock_client):
        results = source.fetch_all(["topic"])

    assert results == []
