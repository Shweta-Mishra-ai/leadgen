"""Apify source — Twitter/X search via a community scraper Actor.

IMPORTANT — use a DEDICATED X account for this, not your personal one:
Search mode on this Actor requires a logged-in X session (auth_token + ct0
cookies). If X detects automated scraping tied to a session, that account
eats the consequence. A throwaway account isolates that risk from your
real one. Cookies expire every few weeks — you'll need to refresh
APIFY_TWITTER_COOKIE periodically.

COST MATH (stay inside the $5/month free credit):
  $0.005 per run-start + $0.003 per tweet returned.
  One run/day covering all topics in one call (single run-start fee):
    9 topics x maxResults=5 = up to 45 tweets/day
    = (45 x $0.003 + $0.005) x 30 days ≈ $4.20/month — fits free tier
  Raise APIFY_MAX_RESULTS_PER_TOPIC only after checking your actual
  Apify usage dashboard — it's easy to blow past $5 without noticing.
  Also set "Maximum charge per run" in the Apify Console as a hard cap.
"""

from __future__ import annotations

import logging

from leadgen.sources.base import LeadSource

logger = logging.getLogger("leadgen.sources.apify")

DEFAULT_ACTOR_ID = "automation-lab/twitter-scraper"


class ApifySource(LeadSource):
    name = "apify"

    def __init__(self, api_token: str | None, twitter_cookie: str | None,
                 actor_id: str = DEFAULT_ACTOR_ID, max_results_per_topic: int = 5,
                 **kwargs):
        super().__init__(**kwargs)
        self.api_token = api_token
        self.twitter_cookie = twitter_cookie
        self.actor_id = actor_id
        self.max_results_per_topic = max_results_per_topic
        self._client = None

    def is_configured(self) -> bool:
        # both are required — search mode is useless without cookies
        return bool(self.api_token and self.twitter_cookie)

    def _get_client(self):
        if self._client is None:
            from apify_client import ApifyClient
            self._client = ApifyClient(self.api_token)
        return self._client

    def fetch_all(self, topics: list[str]) -> list:
        # Overrides the per-topic base loop: one Actor run covers ALL
        # topics at once, so we pay the $0.005 run-start fee only once
        # per pipeline run instead of once per topic.
        if not self.is_configured():
            logger.info("source=apify skipped (not configured)")
            return []
        from leadgen.models import RawLead

        client = self._get_client()
        try:
            from datetime import timedelta
            from decimal import Decimal
            run = client.actor(self.actor_id).call(
                run_input={
                    "mode": "search",
                    "searchTerms": topics,
                    "searchMode": "Latest",
                    "maxResults": self.max_results_per_topic,
                    "twitterCookie": self.twitter_cookie,
                },
                run_timeout=timedelta(seconds=self.timeout_seconds * 2),
                # hard spend cap per run — was $0.15, right at the edge of
                # the estimated ~$0.135-0.14/run cost, likely aborting runs
                # early. $0.25 gives real headroom; watch your Apify usage
                # dashboard and tighten this back down if it's ever exceeded
                max_total_charge_usd=Decimal("0.25"),
            )
        except Exception as e:  # noqa: BLE001 - never let this crash the pipeline
            logger.error("source=apify actor run failed: %s", e)
            return []

        if run is None:
            logger.error("source=apify actor run returned no result")
            return []

        run_status = run.get("status", "UNKNOWN")
        if run_status != "SUCCEEDED":
            logger.warning(
                "source=apify run finished with status=%s (not SUCCEEDED) — "
                "results may be partial or empty. Check the Apify Console "
                "'Runs' tab for the actual reason (e.g. spend cap hit, "
                "cookie rejected, actor error).",
                run_status,
            )

        results = []
        try:
            items = client.dataset(run["defaultDatasetId"]).list_items().items
        except Exception as e:  # noqa: BLE001
            logger.error("source=apify dataset fetch failed: %s", e)
            return []

        for item in items:
            if item.get("type") != "tweet":
                continue
            url = item.get("url", "")
            if not url:
                continue
            try:
                results.append(RawLead.model_validate({
                    "source": "apify_twitter",
                    "title": (item.get("text", "") or "")[:200],
                    "url": url,
                    "snippet": item.get("text", "") or "",
                    "created": item.get("createdAt", "") or "",
                }))
            except Exception as e:  # noqa: BLE001
                logger.warning("apify dropped invalid row: %s", e)

        return results

    def _fetch_topic(self, topic: str) -> list[dict]:
        raise NotImplementedError("ApifySource overrides fetch_all instead")
