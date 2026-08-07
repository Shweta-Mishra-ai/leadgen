"""Automated multi-stage follow-up drip campaign engine.

Follow-up schedule:
    Stage 1 — Day 3  : Short friendly reminder, same value
    Stage 2 — Day 7  : New angle (social proof / different benefit)
    Stage 3 — Day 14 : Final gentle close, no pressure
"""
from __future__ import annotations

import logging

from leadgen.config import Settings
from leadgen.email_sender import send_email
from leadgen.storage import LeadStore

logger = logging.getLogger("leadgen.followup")

# (days_since_last, stage_number)
FOLLOWUP_SCHEDULE: list[tuple[int, int]] = [
    (3, 1),
    (7, 2),
    (14, 3),
]


def _stage_message(sender_name: str, lead_title: str, stage: int) -> tuple[str, str]:
    """Generates stage-specific follow-up subject + body."""
    if stage == 1:
        subj = f"Re: {lead_title[:45]}"
        body = (
            f"Hello,\n\n"
            f"Just circling back on my earlier note about '{lead_title}'.\n\n"
            f"Happy to share a quick solution if you have 10 minutes this week.\n\n"
            f"Best,\n{sender_name}"
        )
    elif stage == 2:
        subj = f"One more thought — {lead_title[:40]}"
        body = (
            f"Hello,\n\n"
            f"Wanted to follow up once more on '{lead_title}'.\n\n"
            f"I've helped similar teams cut delivery time by 40%+ on this exact type of project. "
            f"If timing is off right now, I'm happy to reconnect whenever it suits you.\n\n"
            f"Best,\n{sender_name}"
        )
    else:  # stage == 3, final
        subj = f"Last note — {lead_title[:42]}"
        body = (
            f"Hello,\n\n"
            f"This will be my last follow-up regarding '{lead_title}'.\n\n"
            f"If you ever need help with this or a future project, feel free to reach out anytime — "
            f"no pressure at all.\n\n"
            f"Wishing you the best,\n{sender_name}"
        )
    return subj, body


def process_pending_followups(settings: Settings, store: LeadStore) -> dict[str, int]:
    """Runs all 3 follow-up stages and returns a count per stage.

    Returns:
        dict like {"stage_1": 2, "stage_2": 1, "stage_3": 0}
    """
    results: dict[str, int] = {"stage_1": 0, "stage_2": 0, "stage_3": 0}

    if not settings.gmail_address or not settings.gmail_app_password:
        logger.warning("Gmail credentials missing — skipping follow-up drip.")
        return results

    for days_since, stage in FOLLOWUP_SCHEDULE:
        pending = store.get_pending_followups(days_since=days_since, stage=stage)
        logger.info("Stage %d (%d-day): %d lead(s) eligible", stage, days_since, len(pending))

        for log in pending:
            recipient = log.get("recipient_email", "")
            lead_url = log.get("lead_url", "")
            lead_title = log.get("subject", "your project").replace("Re: ", "").strip()

            if not recipient:
                continue

            subj, body = _stage_message(settings.sender_name, lead_title, stage)
            sent = send_email(settings, recipient, subj, body)

            if sent:
                store.log_outreach(
                    lead_url=lead_url,
                    recipient_email=recipient,
                    subject=subj,
                    body=body,
                    status="sent",
                    followup_stage=stage,
                )
                results[f"stage_{stage}"] += 1
                logger.info(
                    "Stage %d follow-up sent to %s (lead: %s)", stage, recipient, lead_url
                )

    return results


# Keep backward-compatible alias used by telegram_bot.py
def generate_followup_message(
    sender_name: str, client_name: str, lead_title: str, stage: int = 1
) -> tuple[str, str]:
    """Generates a single follow-up message for the given stage."""
    subj, body = _stage_message(sender_name, lead_title, stage)
    if client_name:
        body = body.replace("Hello,", f"Hello {client_name},")
    return subj, body
