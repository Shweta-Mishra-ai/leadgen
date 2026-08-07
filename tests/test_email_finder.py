from __future__ import annotations

from unittest.mock import patch

from leadgen.email_finder import (
    check_domain_has_mx,
    extract_emails_from_text,
    find_contact_email_for_lead,
)


def test_extract_emails_from_text():
    text = "Please reach out to client.john@company.io for details or call us."
    emails = extract_emails_from_text(text)
    assert emails == ["client.john@company.io"]


def test_extract_emails_ignores_noreply():
    text = "Contact noreply@domain.com or founder@myagency.com"
    emails = extract_emails_from_text(text)
    assert emails == ["founder@myagency.com"]


def test_find_contact_email_direct():
    email = find_contact_email_for_lead(
        "Need Developer", "https://example.com", "Send resume to hire@startup.org"
    )
    assert email == "hire@startup.org"


def test_check_domain_has_mx():
    assert check_domain_has_mx("google.com") is True
    assert check_domain_has_mx("nonexistent-domain-12345xyz.org") is False


# Regression test for a real send: /autoemail found no direct/GitHub/DDG
# email for a developer.ibm.com article and fell back to guessing
# "contact@developer.ibm.com" — a fabricated address that was never
# verified to exist, only that the domain accepts mail *somewhere*. That
# guess got used as if it were a real discovered contact and an actual
# outreach email was sent to it.

def test_find_contact_email_does_not_guess_by_default():
    with patch("leadgen.email_finder.DuckDuckGoSource") as mock_ddg_cls, \
         patch("leadgen.email_finder.check_domain_has_mx", return_value=True):
        mock_ddg_cls.return_value.fetch_all.return_value = []
        email = find_contact_email_for_lead(
            "Token optimization: the backbone of prompt engineering",
            "https://developer.ibm.com/articles/awb-token-optimization",
            "No email in this snippet either.",
        )
    assert email is None


def test_find_contact_email_guess_is_opt_in():
    with patch("leadgen.email_finder.DuckDuckGoSource") as mock_ddg_cls, \
         patch("leadgen.email_finder.check_domain_has_mx", return_value=True):
        mock_ddg_cls.return_value.fetch_all.return_value = []
        email = find_contact_email_for_lead(
            "Some article", "https://example-vendor.com/post", "No email here.",
            allow_guess=True,
        )
    assert email == "contact@example-vendor.com"
