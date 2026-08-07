from __future__ import annotations

from leadgen.superpowers import SuperpowerRegistry


def test_superpower_registry_list():
    registry = SuperpowerRegistry()
    skills = registry.list_superpowers()
    assert "TDD_VERIFIER" in skills
    assert "SYSTEMATIC_REVIEWER" in skills
    assert "GROWTH_STACK" in skills


def test_superpower_review_audit():
    registry = SuperpowerRegistry()
    subj, body, passed = registry.apply_superpower_review(
        "Dear Client", "Dear Client, I hope this email finds you well. Here is solution."
    )
    assert "Dear" not in subj
    assert "Dear" not in body
    assert "I hope this email finds you well" not in body
    assert "Hello Client" in body
    assert passed is False
