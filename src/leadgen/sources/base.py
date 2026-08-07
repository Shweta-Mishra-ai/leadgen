"""Base class every source implements. Centralizes the error-handling
policy so individual sources stay short and can't accidentally skip it:

- retry with exponential backoff on transient errors (tenacity)
- per-topic isolation: one topic failing doesn't stop the others
- structured logging on every failure, never a silent swallow
- a source that fails on ALL topics returns [] rather than raising,
  so the pipeline can continue with whatever other sources are healthy
"""

from __future__ import annotations

import abc
import logging

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from leadgen.models import RawLead

logger = logging.getLogger("leadgen.sources")

RETRYABLE_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)


def with_retry(max_retries: int):
    """Shared retry policy: exponential backoff, only on transient errors.
    Validation errors, auth errors etc. are NOT retried — retrying a bad
    API key just burns quota for the same failure."""
    return retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        reraise=True,
    )


class LeadSource(abc.ABC):
    """One external source of leads (Grok, Gemini, Reddit, DDG, ...)."""

    name: str = "base"

    def __init__(self, max_retries: int = 3, timeout_seconds: int = 45):
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Return False if required keys are missing — pipeline skips silently."""

    @abc.abstractmethod
    def _fetch_topic(self, topic: str) -> list[dict]:
        """Fetch raw results (as dicts) for one topic. May raise — the
        wrapper in fetch_all() handles retry/isolation."""

    def fetch_all(self, topics: list[str]) -> list[RawLead]:
        if not self.is_configured():
            logger.info("source=%s skipped (not configured)", self.name)
            return []

        results: list[RawLead] = []
        consecutive_failures = 0
        for topic in topics:
            # simple circuit breaker: if this source has failed 3 topics
            # in a row, stop hammering it for the rest of this run
            if consecutive_failures >= 3:
                logger.warning(
                    "source=%s circuit open, skipping remaining topics", self.name
                )
                break
            try:
                fetch_with_retry = with_retry(self.max_retries)(self._fetch_topic)
                raw_items = fetch_with_retry(topic)
                consecutive_failures = 0
                for item in raw_items:
                    try:
                        results.append(RawLead.model_validate(item))
                    except Exception as e:  # noqa: BLE001 - validation errors, log & skip row
                        logger.warning(
                            "source=%s topic=%r dropped invalid row: %s",
                            self.name, topic, e,
                        )
            except Exception as e:  # noqa: BLE001 - never let one source kill the run
                consecutive_failures += 1
                logger.error(
                    "source=%s topic=%r failed after retries: %s",
                    self.name, topic, e,
                )
        return results
