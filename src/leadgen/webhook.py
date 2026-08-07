from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Any

from leadgen.config import Settings

logger = logging.getLogger("leadgen.webhook")


def send_lead_webhook(settings: Settings, lead_data: dict[str, Any]) -> bool:
    """Dispatches a high-score lead payload to an external webhook (n8n, Make, Slack, Discord)."""
    webhook_url = getattr(settings, "webhook_url", None) or getattr(settings, "WEBHOOK_URL", None)
    if not webhook_url:
        logger.debug("No WEBHOOK_URL configured, skipping webhook dispatch.")
        return False

    payload = {
        "event": "high_score_lead_found",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lead": {
            "title": lead_data.get("title"),
            "url": lead_data.get("url"),
            "score": lead_data.get("score"),
            "category": lead_data.get("category"),
            "snippet": lead_data.get("snippet"),
            "email_found": lead_data.get("email_found"),
            "tech_stack": lead_data.get("tech_stack", []),
        },
        "sender": {
            "name": settings.sender_name,
            "gmail": settings.gmail_address,
        },
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "LeadGen-Bot/2.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 201, 202, 204):
                logger.info("Webhook successfully dispatched to %s", webhook_url)
                return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to dispatch webhook to %s: %s", webhook_url, e)

    return False
