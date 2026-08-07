from __future__ import annotations

from leadgen.marketing_skills import FRAMEWORKS, get_framework_instruction


def test_frameworks_defined():
    assert "PAS" in FRAMEWORKS
    assert "BAB" in FRAMEWORKS
    assert "DIRECT" in FRAMEWORKS


def test_get_framework_instruction():
    pas_instr = get_framework_instruction("PAS")
    assert "Problem - Agitate - Solve" in pas_instr

    fallback_instr = get_framework_instruction("UNKNOWN")
    assert "Direct 1-on-1 Developer" in fallback_instr
