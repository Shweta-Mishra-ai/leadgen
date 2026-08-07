from __future__ import annotations

import logging

from leadgen.sources.base import LeadSource

logger = logging.getLogger("leadgen.sources.tavily")


class TavilySource(LeadSource):
    """Free tier: 1,000 search credits/month, permanent, no card needed.
    Returns clean structured results directly — no LLM needed to parse
    JSON out of a chat response, which makes this the most reliable
    source in the pipeline. Runs two calls per topic (general web +
    reddit.com-scoped) for better Reddit coverage while Reddit's own
    API approval is pending — well within the free 1,000/month budget
    at typical daily-run volume."""

    name = "tavily"

    def __init__(self, api_key: str | None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from tavily import TavilyClient
            self._client = TavilyClient(api_key=self.api_key)
        return self._client

    def _fetch_topic(self, topic: str) -> list[dict]:
        client = self._get_client()
        results = []

        # General web pass
        resp = client.search(
            query=topic, search_depth="basic", max_results=10, topic="general",
        )
        for r in resp.get("results", []):
            results.append({
                "source": "tavily_web",
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": (r.get("content", "") or "")[:300],
                "created": r.get("published_date", "") or "",
            })

        # Reddit-scoped pass — substitutes for official Reddit API while approval is pending
        resp_reddit = client.search(
            query=topic, search_depth="basic", max_results=10, topic="general",
            include_domains=["reddit.com"],
        )
        for r in resp_reddit.get("results", []):
            results.append({
                "source": "tavily_reddit",
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": (r.get("content", "") or "")[:300],
                "created": r.get("published_date", "") or "",
            })

        return [r for r in results if r["url"]]
