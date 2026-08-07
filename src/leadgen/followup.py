from __future__ import annotations

import logging

from leadgen.config import Settings
from leadgen.email_sender import send_email
from leadgen.storage import LeadStore

logger = logging.getLogger("leadgen.followup")


def generate_followup_message(sender_name: str, client_name: str, lead_title: str) -> tuple[str, str]:
    """Generates a concise 1-sentence follow-up message (no AI filler, no links, Hello greeting)."""
    subj = f"Quick follow-up re: {lead_title[:40]}"
    body = (
        f"Hello {client_name or 'there'},\n\n"
        f"Just following up to see if you had a chance to review my note regarding '{lead_title}'. "
        f"Happy to share a quick solution if you have 5 minutes this week.\n\n"
        f"Best,\n{sender_name}"
    )
    return subj, body


def process_pending_followups(settings: Settings, store: LeadStore) -> int:
    """Processes pending follow-up outreach emails from store."""
    logs = store.all_outreach_logs()
    sent_count = 0
    for log in logs:
        # Check if status is sent and target email is valid
        if log.get("status") == "sent" and log.get("recipient_email"):
            target_email = log["recipient_email"]
            subj, body = generate_followup_message(settings.sender_name, "", "your project")
            if settings.gmail_address and settings.gmail_app_password:
                ok = send_email(settings, target_email, subj, body)
                if ok:
                    store.log_outreach(log["lead_url"], target_email, subj, body, status="followup_sent")
                    sent_count += 1
    return sent_count
