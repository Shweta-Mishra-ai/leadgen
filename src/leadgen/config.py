"""Startup configuration and validation.

Fails fast and loud if the environment is unusable — e.g. zero search
sources configured — instead of silently running a no-op pipeline.
"""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    xai_api_key: str | None = Field(default=None, alias="XAI_API_KEY")
    xai_model: str = Field(default="grok-2-latest", alias="XAI_MODEL")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")

    # Apify — Twitter/X search via a community scraper. Requires a DEDICATED
    # X account's session cookies, not your personal account (see
    # sources/apify_source.py for why). Both fields required together.
    apify_api_token: str | None = Field(default=None, alias="APIFY_API_TOKEN")
    apify_twitter_cookie: str | None = Field(default=None, alias="APIFY_TWITTER_COOKIE")
    apify_max_results_per_topic: int = Field(default=5, alias="APIFY_MAX_RESULTS_PER_TOPIC")

    reddit_client_id: str | None = Field(default=None, alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str | None = Field(default=None, alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="leadgen/1.0", alias="REDDIT_USER_AGENT")

    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")

    # NOTE: Groq (console.groq.com) is NOT the same as Grok/xAI (console.x.ai).
    # Groq is a fast-inference host for open models (Llama, etc.) — free tier,
    # no card needed, but no live web/X search. Used here for drafting only.
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")

    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="meta-llama/llama-3.3-70b-instruct:free", alias="OPENROUTER_MODEL"
    )

    # Load / rate-handling knobs — safe defaults, overridable via env
    source_timeout_seconds: int = Field(default=45, alias="SOURCE_TIMEOUT_SECONDS")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    max_concurrent_sources: int = Field(default=4, alias="MAX_CONCURRENT_SOURCES")
    top_n_for_drafts: int = Field(default=15, alias="TOP_N_FOR_DRAFTS")

    db_path: str = Field(default="leads.db", alias="LEADGEN_DB_PATH")

    @model_validator(mode="after")
    def at_least_one_source(self) -> Settings:
        has_grok = bool(self.xai_api_key)
        has_gemini = bool(self.gemini_api_key)
        has_tavily = bool(self.tavily_api_key)
        has_apify = bool(self.apify_api_token and self.apify_twitter_cookie)
        has_reddit = bool(self.reddit_client_id and self.reddit_client_secret)
        # DuckDuckGo needs no key so it's always available; still warn if
        # it's the ONLY source since it's an unofficial best-effort source.
        if not (has_grok or has_gemini or has_tavily or has_apify or has_reddit):
            import warnings
            warnings.warn(
                "No paid/official source keys configured — running on "
                "DuckDuckGo only, which is unofficial and best-effort. "
                "Add XAI_API_KEY, GEMINI_API_KEY, TAVILY_API_KEY, "
                "APIFY_API_TOKEN+APIFY_TWITTER_COOKIE, or REDDIT_CLIENT_ID "
                "for reliable results.",
                stacklevel=2,
            )
        return self

    def active_source_names(self) -> list[str]:
        names = []
        if self.xai_api_key:
            names.append("grok")
        if self.gemini_api_key:
            names.append("gemini")
        if self.tavily_api_key:
            names.append("tavily")
        if self.apify_api_token and self.apify_twitter_cookie:
            names.append("apify")
        if self.reddit_client_id and self.reddit_client_secret:
            names.append("reddit")
        names.append("reddit_public")
        names.append("duckduckgo")
        return names


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
