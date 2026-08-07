from __future__ import annotations

from unittest.mock import MagicMock, patch

from leadgen.config import Settings
from leadgen.email_sender import send_email
from leadgen.humanizer import generate_humanized_email


def test_send_email_fails_without_credentials():
    settings = Settings(_env_file=None, GMAIL_ADDRESS=None, GMAIL_APP_PASSWORD=None)
    assert send_email(settings, "test@example.com", "Subj", "Body") is False


def test_send_email_success_mocked():
    settings = Settings(
        _env_file=None,
        GMAIL_ADDRESS="sender@gmail.com",
        GMAIL_APP_PASSWORD="app-password",
        SENDER_NAME="Shweta",
    )
    with patch("smtplib.SMTP") as mock_smtp:
        server_inst = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server_inst
        result = send_email(settings, "client@example.com", "Hello", "Body text")
        assert result is True
        assert server_inst.send_message.call_count == 1


def test_humanizer_fallback_without_client():
    settings = Settings(_env_file=None)
    subj, body = generate_humanized_email(settings, "Need Python Dev", "Looking for senior dev")
    assert "Need Python Dev" in subj or "Need Python Dev" in body
    assert len(body) > 20
