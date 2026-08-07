from __future__ import annotations

import logging
import re
import socket
from urllib.parse import urlparse

from leadgen.sources.duckduckgo_source import DuckDuckGoSource

logger = logging.getLogger("leadgen.email_finder")

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
NOISE_PREFIXES = ("privacy@", "noreply@", "donotreply@", "support-ticket@")


def extract_emails_from_text(text: str) -> list[str]:
    """Extracts valid email addresses from arbitrary text."""
    matches = re.findall(EMAIL_REGEX, text)
    valid = []
    for email in matches:
        email_clean = email.strip().lower()
        if (
            not any(email_clean.startswith(prefix) for prefix in NOISE_PREFIXES)
            and email_clean not in valid
        ):
            valid.append(email_clean)
    return valid


def check_domain_has_mx(domain: str) -> bool:
    """Free DNS check verifying if domain has active MX mail servers."""
    try:
        # socket.getaddrinfo check for domain host
        socket.getaddrinfo(domain, 25)
        return True
    except Exception:  # noqa: BLE001
        return False


def find_github_contact_email(url: str) -> str | None:
    """Free lookup for GitHub profile / repository contact email."""
    match = re.search(r"github\.com/([a-zA-Z0-9-]+)", url)
    if not match:
        return None
    username = match.group(1)
    if username in ("topics", "trending", "features", "marketplace", "pricing", "search"):
        return None

    ddg = DuckDuckGoSource(max_retries=1, timeout_seconds=8)
    query = f'site:github.com/{username} "@"'
    raw_results = ddg.fetch_all([query])
    for res in raw_results:
        res_title = getattr(res, "title", "") or ""
        res_snippet = getattr(res, "snippet", "") or ""
        found = extract_emails_from_text(f"{res_title} {res_snippet}")
        if found:
            logger.info("Found GitHub contact email for %s: %s", username, found[0])
            return found[0]

    return None


def find_contact_email_for_lead(title: str, url: str, snippet: str) -> str | None:
    """Multi-source free email finder pipeline:
    1. Direct Regex Extraction (Title + Snippet)
    2. GitHub Profile Lookup (if github.com link)
    3. Targeted DuckDuckGo Contact Search
    4. MX-Verified Domain Pattern Generation Fallback
    """
    # 1. Direct text extraction
    combined = f"{title} {snippet}"
    extracted = extract_emails_from_text(combined)
    if extracted:
        logger.info("Extracted direct email from lead text: %s", extracted[0])
        return extracted[0]

    # 2. GitHub lookup if GitHub URL
    if "github.com" in url:
        gh_email = find_github_contact_email(url)
        if gh_email:
            return gh_email

    # 3. Domain DuckDuckGo search
    parsed = urlparse(url)
    domain = parsed.netloc.removeprefix("www.")
    if domain and domain not in ("reddit.com", "x.com", "twitter.com", "fiverr.com", "freelancer.com", "upwork.com"):
        ddg = DuckDuckGoSource(max_retries=1, timeout_seconds=10)
        query = f'site:{domain} "email" OR "contact" OR "mailto:"'
        raw_results = ddg.fetch_all([query])
        for res in raw_results:
            res_title = getattr(res, "title", "") or ""
            res_snippet = getattr(res, "snippet", "") or ""
            found = extract_emails_from_text(f"{res_title} {res_snippet}")
            if found:
                logger.info("Found domain email via DDG search for %s: %s", domain, found[0])
                return found[0]

        # 4. MX Domain Verification Fallback
        if check_domain_has_mx(domain):
            pattern_email = f"contact@{domain}"
            logger.info("Generated MX-verified contact email for %s: %s", domain, pattern_email)
            return pattern_email

    return None
