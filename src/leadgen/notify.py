from __future__ import annotations

import logging

import requests

logger = logging.getLogger("leadgen.notify")


def send_telegram_message(bot_token: str | None, chat_id: str | None,
                          text: str, parse_mode: str = "HTML", timeout: int = 30) -> bool:
    if not bot_token or not chat_id:
        logger.info("Telegram not configured, skipping message delivery")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(
            url,
            data={"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True},
            timeout=timeout,
        )
        resp.raise_for_status()
        return True
    except requests.HTTPError as e:
        # Telegram's actual reason ("chat not found", "can't parse entities",
        # etc.) is in the response body, which raise_for_status() discards —
        # without this every failure looked identical in the logs.
        logger.error("Telegram message delivery failed: %s | response=%s", e, resp.text[:500])
        return False
    except Exception as e:  # noqa: BLE001
        logger.error("Telegram message delivery failed: %s", e)
        return False


def send_telegram_file(bot_token: str | None, chat_id: str | None,
                        filepath: str, caption: str = "", parse_mode: str = "HTML", timeout: int = 30) -> bool:
    if not bot_token or not chat_id:
        logger.info("Telegram not configured, skipping delivery")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
            data["parse_mode"] = parse_mode
        with open(filepath, "rb") as f:
            resp = requests.post(
                url,
                data=data,
                files={"document": f},
                timeout=timeout,
            )
        resp.raise_for_status()
        return True
    except requests.HTTPError as e:
        logger.error("Telegram delivery failed: %s | response=%s", e, resp.text[:500])
        return False
    except Exception as e:  # noqa: BLE001 - notification failure must not crash the run
        logger.error("Telegram delivery failed: %s", e)
        return False
