"""Reddit via public JSON endpoints — NO official API key needed.

Reddit exposes the same post data through public URLs like
reddit.com/r/<subreddit>/new.json — no OAuth, no app registration, no
approval wait. Requires only a descriptive User-Agent header (Reddit
blocks generic/missing ones with 429s).

This is unofficial — not the sanctioned API path, and Reddit could change
or block this at any time without notice. Treat it as a bridge until (or
instead of) official approval, not a permanent guarantee. Being read-only
and modest in request volume keeps it well inside reasonable-use norms.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import requests

from leadgen.sources.base import LeadSource

logger = logging.getLogger("leadgen.sources.reddit_public")

SUBREDDITS = [
    "forhire", "freelance_forhire", "slavelabour", "artificial",
    "MachineLearning", "OpenAI", "SaaS", "Entrepreneur",
]


class RedditPublicSource(LeadSource):
    """Always configured — no key required. Genuinely free, no signup."""

    name = "reddit_public"

    def __init__(self, niche_keywords: list[str],
                 user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                 **kwargs):
        super().__init__(**kwargs)
        self.niche_keywords = niche_keywords
        self.user_agent = user_agent

    def is_configured(self) -> bool:
        return True

    def fetch_all(self, topics: list[str]) -> list:
        # Overrides the per-topic loop: this scans subreddits, not topics,
        # same shape as the official RedditSource.
        from leadgen.models import RawLead

        results = []
        consecutive_failures = 0
        for sub_name in SUBREDDITS:
            if consecutive_failures >= 3:
                logger.warning("source=reddit_public circuit open, skipping rest")
                break
            try:
                posts = self._fetch_subreddit_new(sub_name)
                consecutive_failures = 0
            except Exception as e:  # noqa: BLE001
                consecutive_failures += 1
                logger.error("source=reddit_public r/%s failed: %s", sub_name, e)
                continue

            for post in posts:
                text = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
                if not any(kw in text for kw in self.niche_keywords):
                    continue
                try:
                    created_ts = post.get("created_utc")
                    created_iso = (
                        datetime.fromtimestamp(created_ts, tz=UTC).isoformat()
                        if created_ts
                        else ""
                    )
                    results.append(RawLead.model_validate({
                        "source": "reddit_public",
                        "title": post.get("title", ""),
                        "url": f"https://reddit.com{post.get('permalink', '')}",
                        "snippet": (post.get("selftext", "") or "")[:300],
                        "created": created_iso,
                    }))
                except Exception as e:  # noqa: BLE001
                    logger.warning("reddit_public dropped invalid row: %s", e)
        return results

    def _fetch_subreddit_new(self, subreddit: str) -> list[dict]:
        url = f"https://www.reddit.com/r/{subreddit}/new.json"
        resp = requests.get(
            url,
            headers={"User-Agent": self.user_agent},
            params={"limit": 50},
            timeout=self.timeout_seconds,
        )
        if resp.status_code in (403, 429):
            logger.warning("source=reddit_public r/%s blocked/rate limited (%s)", subreddit, resp.status_code)
            return []
        resp.raise_for_status()
        data = resp.json()
        return [child["data"] for child in data.get("data", {}).get("children", [])]

    def _fetch_topic(self, topic: str) -> list[dict]:
        raise NotImplementedError("RedditPublicSource overrides fetch_all instead")
