from __future__ import annotations

import logging
import sys

from leadgen.config import get_settings
from leadgen.logging_config import configure_logging
from leadgen.storage import LeadStore
from leadgen.telegram_bot import TelegramBot

logger = logging.getLogger("leadgen.cli")


def main() -> int:
    configure_logging()
    try:
        settings = get_settings()
    except Exception as e:  # noqa: BLE001
        logger.error("Configuration error: %s", e)
        return 1

    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is missing.")
        return 1

    store = LeadStore(settings.db_path)
    bot = TelegramBot(settings, store)
    logger.info("Starting Telegram Bot listener...")
    try:
        bot.run_polling()
    except KeyboardInterrupt:
        logger.info("Telegram Bot stopped by user.")
        return 0
    except Exception as e:  # noqa: BLE001
        logger.error("Telegram Bot crashed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
