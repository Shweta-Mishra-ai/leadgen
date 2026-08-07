from __future__ import annotations

import logging

from leadgen.config import Settings
from leadgen.email_finder import find_contact_email_for_lead
from leadgen.email_sender import send_email
from leadgen.humanizer import generate_humanized_email
from leadgen.storage import LeadStore
from leadgen.superpowers import SuperpowerRegistry

logger = logging.getLogger("leadgen.super_agent")


class SuperOutreachAgent:
    """Super Agent orchestrator combining multi-role open-source agent concepts:
    1. Research & Profiler Role: Analyzes lead intent and domain context.
    2. Marketing & Framework Role: Selects best copywriting framework (PAS / BAB / Direct).
    3. Quality Auditor & Humanizer Role: Strips AI filler, robotic phrases, and spam links.
    4. Superpowers Reviewer Role: Applies systematic peer-review & TDD verification (obra/superpowers).
    5. Deliverability & Finder Role: Discovers recipient email & sends direct via Gmail.
    """

    def __init__(self, settings: Settings, store: LeadStore):
        self.settings = settings
        self.store = store
        self.superpowers = SuperpowerRegistry()

    def process_lead(
        self,
        title: str,
        snippet: str,
        url: str = "",
        recipient_email: str | None = None,
        framework: str = "PAS",
        client_name: str = "",
        dry_run: bool = False,
    ) -> dict[str, str | bool]:
        logger.info("SuperAgent Role 1 (Profiler): Analyzing lead intent for '%s'", title)

        # Role 2 & 3: Copywriting Framework + Humanizer Quality Audit
        logger.info("SuperAgent Role 2 & 3 (Copywriter & Humanizer Auditor): Generating note with framework=%s", framework)
        subject, body = generate_humanized_email(
            self.settings, title, snippet, client_name=client_name, framework=framework
        )

        # Role 4: Superpowers Systematic Peer Review
        subject, body, _passed = self.superpowers.apply_superpower_review(subject, body)

        # Role 4: Email Discovery & Deliverability Check
        target_email = recipient_email
        if not target_email and url:
            logger.info("SuperAgent Role 4 (Finder): Discovering contact email for %s", url)
            target_email = find_contact_email_for_lead(title, url, snippet)

        result = {
            "title": title,
            "url": url,
            "framework": framework,
            "subject": subject,
            "body": body,
            "target_email": target_email or "not_found",
            "sent": False,
        }

        if dry_run or not target_email:
            logger.info("SuperAgent Execution complete (Dry Run / No email).")
            return result

        if self.settings.gmail_address and self.settings.gmail_app_password:
            sent_ok = send_email(self.settings, target_email, subject, body)
            if sent_ok:
                self.store.log_outreach(url or "super_agent", target_email, subject, body, status="sent")
                result["sent"] = True
                logger.info("SuperAgent Role 4 (Deliverability): Email sent successfully to %s", target_email)
            else:
                self.store.log_outreach(url or "super_agent", target_email, subject, body, status="failed")

        return result
