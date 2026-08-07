from __future__ import annotations

import pytest

from leadgen.storage import LeadStore


@pytest.fixture
def temp_store(tmp_path):
    db_path = str(tmp_path / "test_leads.db")
    return LeadStore(db_path)
