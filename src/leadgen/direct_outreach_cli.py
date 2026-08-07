from __future__ import annotations

import argparse
import logging
import sys

from leadgen.config import get_settings
from leadgen.email_sender import send_email
from leadgen.humanizer import generate_humanized_email
from leadgen.logging_config import configure_logging
from leadgen.storage import LeadStore

logger = logging.getLogger("leadgen.outreach")


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Send personalized direct outreach emails.")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--lead-id", type=int, help="Lead ID from leads.db")
    parser.add_argument("--title", help="Custom lead title if not specifying lead-id")
    parser.add_argument("--snippet", help="Custom lead snippet if not specifying lead-id")
    parser.add_argument("--client-name", default="", help="Client name if known")
    parser.add_argument("--dry-run", action="store_true", help="Generate & print email without sending")

    args = parser.parse_args()

    try:
        settings = get_settings()
    except Exception as e:  # noqa: BLE001
        logger.error("Configuration error: %s", e)
        return 1

    store = LeadStore(settings.db_path)
    title = args.title or ""
    snippet = args.snippet or ""
    lead_url = "manual_entry"

    if args.lead_id:
        lead = store.get_lead_by_id(args.lead_id)
        if not lead:
            logger.error("Lead with ID %d not found in database.", args.lead_id)
            return 1
        title = lead["title"]
        snippet = lead["snippet"]
        lead_url = lead["url"]

    if not title:
        logger.error("Must provide either --lead-id or --title.")
        return 1

    logger.info("Generating humanized outreach email for: %s", title)
    subject, body = generate_humanized_email(settings, title, snippet, client_name=args.client_name)

    print("\n" + "=" * 60)
    print(f"TO: {args.to}")
    print(f"SUBJECT: {subject}")
    print("-" * 60)
    print(body)
    print("=" * 60 + "\n")

    if args.dry_run:
        logger.info("[Dry Run] Email generated successfully — not sent.")
        return 0

    if not settings.gmail_address or not settings.gmail_app_password:
        logger.error("Gmail credentials missing in environment (GMAIL_ADDRESS & GMAIL_APP_PASSWORD).")
        return 1

    success = send_email(settings, args.to, subject, body)
    if success:
        store.log_outreach(lead_url, args.to, subject, body, status="sent")
        logger.info("Outreach sent and logged to database successfully.")
        return 0
    else:
        store.log_outreach(lead_url, args.to, subject, body, status="failed")
        logger.error("Outreach delivery failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
