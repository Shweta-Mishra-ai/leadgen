from __future__ import annotations

import logging

from leadgen.sources.base import LeadSource

logger = logging.getLogger("leadgen.sources.duckduckgo")

FIXED_TERMS = [
    "hiring freelance content writer technical writer",
    "hiring freelance data analyst python sql",
    "looking for mobile app developer react native flutter",
    "hiring freelance web app developer build software",
    "hiring AI automation freelancer",
    "looking for freelance copywriter",
    "need data analysis freelancer",
]


class DuckDuckGoSource(LeadSource):
    """Free, no-key backup source. Unofficial (no public API) — treated as
    best-effort, always configured, low weight in scoring."""

    name = "duckduckgo"

    def is_configured(self) -> bool:
        return True  # no key required

    def _fetch_topic(self, topic: str) -> list[dict]:
        try:
            from ddgs import DDGS
            from ddgs.exceptions import DDGSException
        except ImportError:
            try:
                from duckduckgo_search import DDGS
                from duckduckgo_search.exceptions import DuckDuckGoSearchException as DDGSException
            except ImportError:
                logger.warning("duckduckgo package not installed")
                return []

        try:
            with DDGS() as ddgs:
                hits = list(ddgs.text(topic, max_results=10))
        except DDGSException as e:
            if "no results" in str(e).lower():
                logger.info("duckduckgo: no results for topic=%r", topic)
                return []
            raise  # a real DDGS error (rate limit, blocked, etc.) — let retry/circuit breaker handle it
        return [
            {
                "source": "duckduckgo",
                "title": h.get("title", ""),
                "url": h.get("href", ""),
                "snippet": h.get("body", "")[:300],
                "created": "",
            }
            for h in hits
            if h.get("href")
        ]

    def fetch_all(self, topics: list[str] | None = None) -> list:
        return super().fetch_all(topics or FIXED_TERMS)
