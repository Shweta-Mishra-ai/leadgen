from __future__ import annotations

from unittest.mock import MagicMock, patch

from leadgen.config import Settings
from leadgen.followup import (
    FOLLOWUP_SCHEDULE,
    _stage_message,
    generate_followup_message,
    process_pending_followups,
)
from leadgen.reply_classifier import classify_email_reply
from leadgen.tech_profiler import detect_lead_tech_stack
from leadgen.webhook import send_lead_webhook


def test_send_lead_webhook_no_url():
    settings = Settings(_env_file=None)
    assert send_lead_webhook(settings, {"title": "Test Lead", "score": 90}) is False


def test_send_lead_webhook_success_mocked():
    settings = Settings(_env_file=None)
    settings.webhook_url = "https://example.com/webhook"
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_url.return_value.__enter__.return_value = mock_resp
        result = send_lead_webhook(settings, {"title": "Python Lead", "score": 95})
        assert result is True


def test_classify_email_reply_out_of_office():
    settings = Settings(_env_file=None)
    res = classify_email_reply(settings, "I am currently out of office until Monday.")
    assert res["intent"] == "OUT_OF_OFFICE"


def test_classify_email_reply_call_requested():
    settings = Settings(_env_file=None)
    res = classify_email_reply(settings, "Sounds great! Are you free for a Zoom call tomorrow?")
    assert res["intent"] == "CALL_REQUESTED"


def test_classify_email_reply_not_interested():
    settings = Settings(_env_file=None)
    res = classify_email_reply(settings, "No thanks, please remove me from your list.")
    assert res["intent"] == "NOT_INTERESTED"


def test_detect_lead_tech_stack():
    stack = detect_lead_tech_stack("Need Python Developer", "Building FastAPI with PostgreSQL and AWS")
    assert "Python" in stack
    assert "Database" in stack
    assert "Cloud/DevOps" in stack


# --- Multi-stage followup tests ---

def test_followup_schedule_has_3_stages():
    assert len(FOLLOWUP_SCHEDULE) == 3
    days = [d for d, _ in FOLLOWUP_SCHEDULE]
    stages = [s for _, s in FOLLOWUP_SCHEDULE]
    assert days == [3, 7, 14]
    assert stages == [1, 2, 3]


def test_stage_1_message_no_pressure():
    subj, body = _stage_message("Shweta", "Build AI Agent", stage=1)
    assert "Build AI Agent" in body
    assert "Hello," in body
    assert "Dear" not in body


def test_stage_2_message_new_angle():
    subj, body = _stage_message("Shweta", "Automation Pipeline", stage=2)
    assert "Automation Pipeline" in body
    assert "40%" in body  # social proof line
    assert "Dear" not in body


def test_stage_3_message_final_close():
    subj, body = _stage_message("Shweta", "Data Scraping", stage=3)
    assert "last follow-up" in body.lower()
    assert "no pressure" in body.lower()
    assert "Dear" not in body


def test_generate_followup_message_with_name():
    subj, body = generate_followup_message("Shweta", "John", "Build AI Agent", stage=1)
    assert "Hello John," in body
    assert "Dear" not in body


def test_generate_followup_message_stage3():
    subj, body = generate_followup_message("Shweta", "", "Data Pipeline", stage=3)
    assert "last follow-up" in body.lower()


def test_process_pending_followups_no_credentials():
    settings = Settings(_env_file=None)
    store = MagicMock()
    store.get_pending_followups.return_value = []
    results = process_pending_followups(settings, store)
    assert results == {"stage_1": 0, "stage_2": 0, "stage_3": 0}
