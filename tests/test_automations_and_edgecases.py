from __future__ import annotations

from unittest.mock import MagicMock, patch

from leadgen.config import Settings
from leadgen.followup import generate_followup_message, process_pending_followups
from leadgen.reply_classifier import classify_email_reply
from leadgen.tech_profiler import detect_lead_tech_stack
from leadgen.webhook import send_lead_webhook


def test_send_lead_webhook_no_url():
    settings = Settings(_env_file=None)
    assert send_lead_webhook(settings, {"title": "Test Lead", "score": 90}) is False


def test_send_lead_webhook_success_mocked():
    settings = Settings(_env_file=None)
    setattr(settings, "webhook_url", "https://example.com/webhook")
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


def test_generate_followup_message():
    subj, body = generate_followup_message("Shweta", "John", "Build AI Agent")
    assert "Build AI Agent" in subj or "Build AI Agent" in body
    assert "Hello John," in body
    assert "Dear" not in body


def test_process_pending_followups():
    settings = Settings(_env_file=None)
    store = MagicMock()
    store.all_outreach_logs.return_value = [
        {"lead_url": "https://example.com", "recipient_email": "client@domain.com", "status": "sent"}
    ]
    sent_count = process_pending_followups(settings, store)
    assert sent_count == 0  # No gmail credentials set
