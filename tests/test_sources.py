from __future__ import annotations

from unittest.mock import patch

from leadgen.sources.base import LeadSource


class FlakySource(LeadSource):
    """Fails on specific topics, used to test isolation & circuit breaker."""
    name = "flaky"

    def __init__(self, fail_topics=None, always_fail=False, **kwargs):
        super().__init__(**kwargs)
        self.fail_topics = fail_topics or set()
        self.always_fail = always_fail
        self.call_log = []

    def is_configured(self) -> bool:
        return True

    def _fetch_topic(self, topic: str) -> list[dict]:
        self.call_log.append(topic)
        if self.always_fail or topic in self.fail_topics:
            raise ConnectionError("simulated transient failure")
        return [{
            "source": "flaky", "title": f"lead for {topic}",
            "url": f"https://example.com/{topic}", "snippet": "x",
        }]


class UnconfiguredSource(LeadSource):
    name = "unconfigured"

    def is_configured(self) -> bool:
        return False

    def _fetch_topic(self, topic: str) -> list[dict]:
        raise AssertionError("should never be called when not configured")


def test_unconfigured_source_returns_empty_without_calling_fetch():
    source = UnconfiguredSource()
    assert source.fetch_all(["topic1"]) == []


def test_one_bad_topic_does_not_block_others():
    source = FlakySource(fail_topics={"bad"}, max_retries=1, timeout_seconds=5)
    results = source.fetch_all(["good1", "bad", "good2"])
    urls = {r.url for r in results}
    assert "https://example.com/good1" in str(urls)
    assert "https://example.com/good2" in str(urls)
    assert len(results) == 2


def test_circuit_breaker_stops_after_three_consecutive_failures():
    source = FlakySource(always_fail=True, max_retries=1, timeout_seconds=5)
    topics = ["t1", "t2", "t3", "t4", "t5"]
    results = source.fetch_all(topics)
    assert results == []
    # circuit opens after 3 consecutive failures, so t4/t5 should never be attempted
    assert source.call_log == ["t1", "t2", "t3"]


def test_retry_recovers_from_transient_failure():
    source = FlakySource(max_retries=3, timeout_seconds=5)
    call_count = {"n": 0}
    original = source._fetch_topic

    def flaky_then_ok(topic):
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise ConnectionError("first attempt fails")
        return original(topic)

    with patch.object(source, "_fetch_topic", side_effect=flaky_then_ok):
        results = source.fetch_all(["topic1"])
    assert len(results) == 1
    assert call_count["n"] == 2  # failed once, succeeded on retry


def test_invalid_row_from_source_is_dropped_not_fatal():
    source = FlakySource(max_retries=1, timeout_seconds=5)
    with patch.object(source, "_fetch_topic", return_value=[{"source": "x", "url": ""}]):
        # empty url fails RawLead validation -> should be dropped, not raise
        results = source.fetch_all(["topic1"])
    assert results == []
