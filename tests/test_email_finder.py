from __future__ import annotations

from leadgen.email_finder import extract_emails_from_text, find_contact_email_for_lead


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
