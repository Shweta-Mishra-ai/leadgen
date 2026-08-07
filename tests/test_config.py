from __future__ import annotations

import warnings

from leadgen.config import Settings


def test_settings_loads_with_no_keys_and_warns(monkeypatch):
    for var in ["XAI_API_KEY", "GEMINI_API_KEY", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"]:
        monkeypatch.delenv(var, raising=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        settings = Settings(_env_file=None)
        assert any("No paid/official source keys" in str(w.message) for w in caught)
    assert settings.active_source_names() == ["reddit_public", "duckduckgo"]


def test_settings_detects_grok_key(monkeypatch):
    settings = Settings(_env_file=None, XAI_API_KEY="test-key")
    assert "grok" in settings.active_source_names()


def test_settings_reddit_needs_both_id_and_secret(monkeypatch):
    settings = Settings(_env_file=None, REDDIT_CLIENT_ID="id-only")
    assert "reddit" not in settings.active_source_names()

    settings2 = Settings(_env_file=None, REDDIT_CLIENT_ID="id", REDDIT_CLIENT_SECRET="secret")
    assert "reddit" in settings2.active_source_names()


def test_settings_defaults_are_sane():
    settings = Settings(_env_file=None)
    assert settings.max_retries >= 1
    assert settings.source_timeout_seconds > 0
    assert settings.max_concurrent_sources >= 1
