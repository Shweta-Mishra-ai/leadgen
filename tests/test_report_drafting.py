from __future__ import annotations

from leadgen.config import Settings
from leadgen.report import _get_draft_client_and_model


def test_prefers_xai_when_all_keys_present():
    settings = Settings(_env_file=None, XAI_API_KEY="xai-key", GROQ_API_KEY="groq-key",
                         OPENROUTER_API_KEY="or-key")
    client, model = _get_draft_client_and_model(settings)
    assert model == "grok-2-latest"
    assert str(client.base_url).startswith("https://api.x.ai")


def test_falls_back_to_groq_when_no_xai():
    settings = Settings(_env_file=None, GROQ_API_KEY="groq-key", OPENROUTER_API_KEY="or-key")
    client, model = _get_draft_client_and_model(settings)
    assert model == "llama-3.3-70b-versatile"
    assert str(client.base_url).startswith("https://api.groq.com")


def test_falls_back_to_openrouter_when_only_that_set():
    settings = Settings(_env_file=None, OPENROUTER_API_KEY="or-key")
    client, _model = _get_draft_client_and_model(settings)
    assert str(client.base_url).startswith("https://openrouter.ai")


def test_no_client_when_nothing_configured():
    settings = Settings(_env_file=None)
    client, model = _get_draft_client_and_model(settings)
    assert client is None
    assert model is None
