"""The orchestrator. Runs every configured source CONCURRENTLY (not
sequentially) with a hard per-source timeout, so one slow API never
stalls the whole pipeline — this is the "load handling" piece: bounded
worker pool, bounded time per source, bounded memory (scores as we go,
doesn't hold everything in a giant unbounded list before writing).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from leadgen.config import Settings
from leadgen.models import RawLead, ScoredLead
from leadgen.sources import (
    ApifySource,
    DuckDuckGoSource,
    GeminiSource,
    GrokSource,
    RedditPublicSource,
    RedditSource,
    TavilySource,
)
from leadgen.sources.base import LeadSource
from leadgen.storage import LeadStore

logger = logging.getLogger("leadgen.pipeline")

NICHE_KEYWORDS = [
    # AI & Automation
    "llm cost optimization", "reduce llm cost", "token optimization",
    "genai engineer", "ai automation freelancer", "generative ai consultant",
    "ai agent developer",
    # Freelance Writing
    "freelance writer", "content writer", "technical writer", "copywriter",
    "writing freelancer", "content writing contract",
    # Data Analysis & Engineering
    "data analyst", "data analysis freelancer", "python data analyst",
    "sql analyst", "data visualization freelancer", "data engineer freelancer",
    # App Development & App Sales
    "app developer freelancer", "mobile app developer", "flutter developer",
    "react native developer", "build an app", "saas app development",
    "custom web app developer",
]

HIRING_SIGNAL_KEYWORDS = [
    "looking for", "hiring", "need help with", "budget", "freelancer",
    "who can build", "recommend someone", "seeking", "looking to hire",
    "budget ready", "dm me", "need developer", "contractor",
]

# Job-board aggregators return category/listing pages, not individual
# hiring requests — a page titled "AI Automation Freelancer Jobs" is a
# search results page, not someone asking to hire. Excluded entirely.
NOISE_DOMAINS = {
    "indeed.com", "ziprecruiter.com", "linkedin.com", "glassdoor.com",
    "freelancer.com", "truelancer.com", "upwork.com", "monster.com",
    "simplyhired.com", "flexjobs.com",
    # tool/vendor marketing sites that rank well for these keywords but
    # are never hiring leads — expect to keep extending this list as
    # new noise patterns show up in real reports
    "litellm.ai", "portkey.ai", "redis.io", "mulesoft.com",
    "truefoundry.com", "solulab.com", "docs.litellm.ai",
    # blog/media/tutorial sites that match keywords without hiring intent
    "medium.com", "dev.to", "github.com", "youtube.com", "coursera.org",
    "udemy.com", "substack.com", "arxiv.org", "towardsdatascience.com",
}

# Listicles, vendor docs, and "how to" guides match keywords well but
# aren't leads — someone publishing "10 Strategies to Reduce LLM Costs"
# isn't asking to hire anyone.
CONTENT_NOISE_PHRASES = [
    "best ", "top 10", "top 5", " vs ", "how to ", "guide to", "guide:",
    "techniques", "strategies", "overview", "documentation", "docs",
    " ways to", "proven ways", "tutorial", "course", "github repository", "awesome-",
]

# Reddit/X posts are individuals talking, not marketing pages — genuine
# hiring intent is far more likely here than on general web results.
PLATFORM_SOURCE_PREFIXES = (
    "reddit", "grok_x", "grok_reddit", "apify_twitter", "tavily_reddit",
)


def _domain_of(url: str) -> str:
    from urllib.parse import urlparse
    netloc = urlparse(url).netloc.lower()
    return netloc.removeprefix("www.")


def score_lead(raw: RawLead) -> int:
    domain = _domain_of(str(raw.url))
    if any(domain == d or domain.endswith("." + d) for d in NOISE_DOMAINS):
        return 0

    text = f"{raw.title} {raw.snippet}".lower()
    title_lower = raw.title.lower()

    niche_hits = sum(1 for kw in NICHE_KEYWORDS if kw in text)
    hiring_hits = sum(1 for kw in HIRING_SIGNAL_KEYWORDS if kw in text)
    noise_hits = sum(1 for phrase in CONTENT_NOISE_PHRASES if phrase in title_lower)

    score = niche_hits * 2 + hiring_hits - (noise_hits * 3)

    if raw.source.startswith(PLATFORM_SOURCE_PREFIXES):
        score += 2  # genuine individual post, weight it up

    return max(score, 0)


def build_sources(settings: Settings) -> list[LeadSource]:
    common = {"max_retries": settings.max_retries, "timeout_seconds": settings.source_timeout_seconds}
    return [
        GrokSource(api_key=settings.xai_api_key, model=settings.xai_model, **common),
        GeminiSource(api_key=settings.gemini_api_key, model=settings.gemini_model, **common),
        TavilySource(api_key=settings.tavily_api_key, **common),
        ApifySource(
            api_token=settings.apify_api_token,
            twitter_cookie=settings.apify_twitter_cookie,
            max_results_per_topic=settings.apify_max_results_per_topic,
            **common,
        ),
        RedditSource(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            niche_keywords=NICHE_KEYWORDS,
            **common,
        ),
        RedditPublicSource(
            niche_keywords=NICHE_KEYWORDS,
            user_agent=settings.reddit_user_agent,
            **common,
        ),
        DuckDuckGoSource(**common),
    ]


def _run_source(source: LeadSource, topics: list[str]) -> list[RawLead]:
    try:
        return source.fetch_all(topics)
    except Exception as e:  # noqa: BLE001 - absolute last resort, a source must
        # NEVER be able to crash the pipeline, even on a bug in the source itself
        logger.error("source=%s crashed unexpectedly: %s", source.name, e)
        return []


def run_pipeline(settings: Settings, store: LeadStore) -> dict:
    """Returns a summary dict: {source_name: raw_count, ..., 'new_leads': N}"""
    sources = build_sources(settings)
    summary: dict = {}

    with ThreadPoolExecutor(max_workers=settings.max_concurrent_sources) as pool:
        futures = {
            pool.submit(_run_source, src, NICHE_KEYWORDS): src
            for src in sources
        }
        all_raw: list[RawLead] = []
        for future, src in futures.items():
            try:
                # hard ceiling even beyond the source's own timeout, in case
                # a retry loop or network stack hangs past its own budget
                raw = future.result(timeout=settings.source_timeout_seconds * settings.max_retries + 30)
            except FutureTimeoutError:
                logger.error("source=%s exceeded hard pipeline timeout, dropping", src.name)
                raw = []
            summary[src.name] = len(raw)
            all_raw.extend(raw)

    scored = [ScoredLead.from_raw(r, score_lead(r)) for r in all_raw]
    scored = [s for s in scored if s.score > 0]  # drop noise below relevance bar

    new_count = store.insert_new(scored)
    summary["raw_total"] = len(all_raw)
    summary["scored_relevant"] = len(scored)
    summary["new_leads"] = new_count
    logger.info("pipeline run complete: %s", summary)
    return summary
