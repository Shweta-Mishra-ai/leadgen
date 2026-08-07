"""Regression tests for the four production failures fixed together:

1. the lead DB never survived a run, so every lead looked new every day
2. /report was advertised in /help but had no handler at all
3. a failing command aborted the rest of the update batch, silently
4. apify-client 3.x returns an object, not a subscriptable dict
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from leadgen.config import Settings
from leadgen.models import ScoredLead
from leadgen.sources.apify_source import _run_field
from leadgen.telegram_bot import OFFSET_KEY, TelegramBot


def _lead(url: str, found_at: str, score: int = 5) -> ScoredLead:
    return ScoredLead(
        source="duckduckgo",
        title=f"lead {url}",
        url=url,
        snippet="needs an automation freelancer",
        score=score,
        created="",
        found_at=found_at,
    )


# --- 1. daily segmentation -------------------------------------------------

def test_leads_found_on_returns_only_that_day(temp_store):
    temp_store.insert_new([
        _lead("https://a.com/1", "2026-08-06T09:00:00+00:00"),
        _lead("https://b.com/2", "2026-08-07T09:00:00+00:00"),
        _lead("https://c.com/3", "2026-08-07T18:30:00+00:00"),
    ])

    today = temp_store.leads_found_on("2026-08-07")

    assert len(today) == 2
    assert {row["url"] for row in today} == {"https://b.com/2", "https://c.com/3"}
    assert len(temp_store.all_leads()) == 3


def test_leads_found_on_empty_day_is_not_an_error(temp_store):
    temp_store.insert_new([_lead("https://a.com/1", "2026-08-06T09:00:00+00:00")])
    assert temp_store.leads_found_on("2026-08-07") == []


def test_dedup_survives_a_second_run(temp_store):
    """The whole point of persisting the DB: the same URL seen tomorrow
    must not come back as a new lead."""
    first = temp_store.insert_new([_lead("https://a.com/1", "2026-08-06T09:00:00+00:00")])
    second = temp_store.insert_new([_lead("https://a.com/1", "2026-08-07T09:00:00+00:00")])

    assert first == 1
    assert second == 0


# --- 2. bot state persistence ---------------------------------------------

def test_state_round_trips_and_overwrites(temp_store):
    assert temp_store.get_state("missing", "fallback") == "fallback"
    temp_store.set_state("k", "1")
    assert temp_store.get_state("k") == "1"
    temp_store.set_state("k", "2")
    assert temp_store.get_state("k") == "2"


def test_bot_resumes_offset_from_store(temp_store):
    temp_store.set_state(OFFSET_KEY, "4242")
    settings = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="token123")

    bot = TelegramBot(settings, temp_store)

    assert bot.offset == 4242


def test_bot_offset_defaults_to_zero_on_garbage(temp_store):
    temp_store.set_state(OFFSET_KEY, "not-a-number")
    settings = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="token123")

    assert TelegramBot(settings, temp_store).offset == 0


def test_process_updates_persists_offset(temp_store):
    settings = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="token123")
    bot = TelegramBot(settings, temp_store)

    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "result": [{"update_id": 7, "message": {"text": "/help", "chat": {"id": 1}}}]
    }

    with patch("leadgen.telegram_bot.requests.get", return_value=resp), \
         patch("leadgen.telegram_bot.send_telegram_message"):
        assert bot.process_updates() == 1

    # A fresh bot (i.e. the next cron run) must not replay update 7.
    assert TelegramBot(settings, temp_store).offset == 8


# --- 3. /report command exists and failures don't go silent ---------------

def test_report_command_is_handled():
    settings = Settings(
        _env_file=None, TELEGRAM_BOT_TOKEN="token123", TELEGRAM_CHAT_ID="999"
    )
    bot = TelegramBot(settings, MagicMock())

    with patch("leadgen.report.generate_report", return_value="leads_report.xlsx") as gen, \
         patch("leadgen.telegram_bot.send_telegram_message") as send, \
         patch("leadgen.telegram_bot.send_telegram_file") as send_file:
        bot.handle_command("999", "/report")

    gen.assert_called_once()
    # Same chat as the configured report target — don't send the file twice.
    send_file.assert_not_called()
    assert "Unknown command" not in send.call_args[0][2]


def test_report_command_sends_file_to_a_different_chat():
    settings = Settings(
        _env_file=None, TELEGRAM_BOT_TOKEN="token123", TELEGRAM_CHAT_ID="999"
    )
    bot = TelegramBot(settings, MagicMock())

    with patch("leadgen.report.generate_report", return_value="leads_report.xlsx"), \
         patch("leadgen.telegram_bot.send_telegram_message"), \
         patch("leadgen.telegram_bot.send_telegram_file") as send_file:
        bot.handle_command("12345", "/report")

    send_file.assert_called_once()


def test_report_command_reports_empty_database_instead_of_crashing():
    settings = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="token123")
    bot = TelegramBot(settings, MagicMock())

    with patch("leadgen.report.generate_report", side_effect=ValueError("No leads found")), \
         patch("leadgen.telegram_bot.send_telegram_message") as send:
        bot.handle_command("12345", "/report")

    assert "No leads found" in send.call_args[0][2]


def test_failing_command_still_processes_the_rest_of_the_batch(temp_store):
    settings = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="token123")
    bot = TelegramBot(settings, temp_store)

    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "result": [
            {"update_id": 1, "message": {"text": "/boom", "chat": {"id": 1}}},
            {"update_id": 2, "message": {"text": "/help", "chat": {"id": 1}}},
        ]
    }
    handled: list[str] = []

    def fake_handle(chat_id, text):
        handled.append(text)
        if text == "/boom":
            raise RuntimeError("kaboom")

    with patch("leadgen.telegram_bot.requests.get", return_value=resp), \
         patch("leadgen.telegram_bot.send_telegram_message") as send, \
         patch.object(bot, "handle_command", side_effect=fake_handle):
        bot.process_updates()

    assert handled == ["/boom", "/help"]
    # The user is told the command blew up rather than getting silence.
    assert any("kaboom" in call[0][2] for call in send.call_args_list)


def test_run_once_stops_when_queue_is_empty(temp_store):
    settings = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="token123")
    bot = TelegramBot(settings, temp_store)

    with patch.object(bot, "process_updates", side_effect=[3, 0]) as proc:
        assert bot.run_once() == 3

    assert proc.call_count == 2


# --- 4. apify-client version compatibility --------------------------------

@pytest.mark.parametrize(
    "run",
    [
        {"defaultDatasetId": "ds123", "status": "SUCCEEDED"},          # client 1.x
        type("Run", (), {"default_dataset_id": "ds123", "status": "SUCCEEDED"})(),  # 3.x
    ],
)
def test_run_field_reads_both_client_shapes(run):
    assert _run_field(run, "defaultDatasetId", "default_dataset_id") == "ds123"


def test_run_field_returns_default_when_absent():
    assert _run_field({}, "defaultDatasetId", "default_dataset_id", "fallback") == "fallback"
