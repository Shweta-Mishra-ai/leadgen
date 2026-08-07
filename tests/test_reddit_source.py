from __future__ import annotations

from unittest.mock import MagicMock, patch

from leadgen.sources.reddit_source import RedditSource

NICHE_KEYWORDS = ["genai engineer", "llm cost optimization"]


def test_reddit_not_configured_without_id_or_secret():
    source = RedditSource(client_id=None, client_secret=None, user_agent="ua", niche_keywords=NICHE_KEYWORDS)
    assert source.is_configured() is False
    assert source.fetch_all(["topic"]) == []


def test_reddit_configured_with_both():
    source = RedditSource(client_id="id", client_secret="secret", user_agent="ua", niche_keywords=NICHE_KEYWORDS)
    assert source.is_configured() is True


def test_reddit_source_filters_by_niche_keywords():
    source = RedditSource(client_id="id", client_secret="secret", user_agent="ua", niche_keywords=NICHE_KEYWORDS)
    mock_reddit = MagicMock()
    mock_post1 = MagicMock()
    mock_post1.title = "Hiring a genai engineer for project"
    mock_post1.selftext = "Budget available"
    mock_post1.permalink = "/r/forhire/comments/123/"
    mock_post1.created_utc = 1700000000.0

    mock_post2 = MagicMock()
    mock_post2.title = "Unrelated post"
    mock_post2.selftext = "Nothing here"
    mock_post2.permalink = "/r/forhire/comments/456/"
    mock_post2.created_utc = 1700000000.0

    mock_reddit.subreddit.return_value.new.return_value = [mock_post1, mock_post2]

    with patch.object(source, "_get_client", return_value=mock_reddit):
        results = source.fetch_all(["topic"])

    assert len(results) >= 1
    assert any("genai" in r.title.lower() for r in results)
