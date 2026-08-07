from __future__ import annotations

import logging
from datetime import UTC, datetime

from leadgen.sources.base import LeadSource

logger = logging.getLogger("leadgen.sources.reddit")

SUBREDDITS = [
    "forhire", "freelance_forhire", "slavelabour", "artificial",
    "MachineLearning", "OpenAI", "SaaS", "Entrepreneur",
]


class RedditSource(LeadSource):
    name = "reddit"

    def __init__(self, client_id: str | None, client_secret: str | None,
                 user_agent: str, niche_keywords: list[str], **kwargs):
        super().__init__(**kwargs)
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.niche_keywords = niche_keywords
        self._reddit = None

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_client(self):
        if self._reddit is None:
            import praw
            self._reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
            self._reddit.read_only = True
        return self._reddit

    def fetch_all(self, topics: list[str]) -> list:
        # scanned by subreddit, not by topic string, so it overrides fetch_all
        # directly rather than using the per-topic base implementation.
        if not self.is_configured():
            logger.info("source=reddit skipped (not configured)")
            return []
        from leadgen.models import RawLead

        reddit = self._get_client()
        results = []
        consecutive_failures = 0
        for sub_name in SUBREDDITS:
            if consecutive_failures >= 3:
                logger.warning("source=reddit circuit open, skipping remaining subreddits")
                break
            try:
                for post in reddit.subreddit(sub_name).new(limit=50):
                    text = f"{post.title} {post.selftext}".lower()
                    if not any(kw in text for kw in self.niche_keywords):
                        continue
                    try:
                        results.append(RawLead.model_validate({
                            "source": "reddit_api",
                            "title": post.title,
                            "url": f"https://reddit.com{post.permalink}",
                            "snippet": post.selftext[:300],
                            "created": datetime.fromtimestamp(
                                post.created_utc, tz=UTC
                            ).isoformat(),
                        }))
                    except Exception as e:  # noqa: BLE001
                        logger.warning("reddit dropped invalid row: %s", e)
                consecutive_failures = 0
            except Exception as e:  # noqa: BLE001
                consecutive_failures += 1
                logger.error("source=reddit subreddit=%r failed: %s", sub_name, e)
        return results

    def _fetch_topic(self, topic: str) -> list[dict]:
        raise NotImplementedError("RedditSource overrides fetch_all instead")
