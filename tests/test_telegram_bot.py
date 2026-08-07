from __future__ import annotations

from unittest.mock import MagicMock, patch

from leadgen.config import Settings
from leadgen.telegram_bot import TelegramBot


def test_telegram_bot_not_configured_without_token():
    settings = Settings(_env_file=None, TELEGRAM_BOT_TOKEN=None)
    store = MagicMock()
    bot = TelegramBot(settings, store)
    assert bot.is_configured() is False


def test_telegram_bot_configured_with_token():
    settings = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="token123")
    store = MagicMock()
    bot = TelegramBot(settings, store)
    assert bot.is_configured() is True


def test_telegram_bot_handle_help_command():
    settings = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="token123")
    store = MagicMock()
    bot = TelegramBot(settings, store)

    with patch("leadgen.telegram_bot.send_telegram_message") as mock_send:
        bot.handle_command("12345", "/help")

    assert mock_send.call_count == 1
    assert "Available Commands" in mock_send.call_args[0][2]


def test_telegram_bot_handle_stats_command():
    settings = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="token123")
    store = MagicMock()
    store.count.return_value = 10
    store.all_leads.return_value = [{"source": "duckduckgo"}, {"source": "grok"}]
    bot = TelegramBot(settings, store)

    with patch("leadgen.telegram_bot.send_telegram_message") as mock_send:
        bot.handle_command("12345", "/stats")

    assert mock_send.call_count == 1
    assert "Total Stored Leads" in mock_send.call_args[0][2]
