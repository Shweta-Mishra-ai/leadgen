from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from leadgen.sources.duckduckgo_source import DuckDuckGoSource

logger = logging.getLogger("leadgen.email_finder")

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
NOISE_EMAILS = {"support@", "info@", "contact@", "privacy@", "sales@", "hello@", "admin@"}


def extract_emails_from_text(text: str) -> list[str]:
    """Extracts valid email addresses from arbitrary text."""
    matches = re.findall(EMAIL_REGEX, text)
    valid = []
    for email in matches:
        email_clean = email.strip().lower()
        # Filter out common generic noise emails unless no others exist
        if not any(email_clean.startswith(prefix) for prefix in ("privacy@", "noreply@", "donotreply@")) and email_clean not in valid:
            valid.append(email_clean)
    return valid


def find_contact_email_for_lead(title: str, url: str, snippet: str) -> str | None:
    """Finds or extracts a contact email address for a lead.

    First checks snippet & title text, then performs targeted DDG search if domain exists.
    """
    # 1. Direct text extraction
    combined = f"{title} {snippet}"
    extracted = extract_emails_from_text(combined)
    if extracted:
        logger.info("Extracted direct email from lead text: %s", extracted[0])
        return extracted[0]

    # 2. Extract domain and search for public email contact
    parsed = urlparse(url)
    domain = parsed.netloc.removeprefix("www.")
    if domain and domain not in ("reddit.com", "x.com", "twitter.com", "fiverr.com", "freelancer.com", "upwork.com"):
        ddg = DuckDuckGoSource(max_retries=1, timeout_seconds=10)
        query = f'site:{domain} "email" OR "contact"'
        raw_results = ddg.fetch_all([query])
        for res in raw_results:
            res_title = getattr(res, "title", "") or ""
            res_snippet = getattr(res, "snippet", "") or ""
            found = extract_emails_from_text(f"{res_title} {res_snippet}")
            if found:
                logger.info("Found domain email via DDG search for %s: %s", domain, found[0])
                return found[0]

    return None
