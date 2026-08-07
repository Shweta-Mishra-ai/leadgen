from __future__ import annotations

from unittest.mock import MagicMock

from leadgen.config import Settings
from leadgen.super_agent import SuperOutreachAgent


def test_super_agent_process_lead_dry_run():
    settings = Settings(_env_file=None)
    store = MagicMock()
    agent = SuperOutreachAgent(settings, store)
    res = agent.process_lead(
        title="Need n8n developer",
        snippet="Looking for developer to build webhooks",
        url="https://example.com/job",
        dry_run=True,
        framework="PAS",
    )
    assert res["title"] == "Need n8n developer"
    assert res["framework"] == "PAS"
    assert "Hello" in res["body"]
    assert res["sent"] is False
