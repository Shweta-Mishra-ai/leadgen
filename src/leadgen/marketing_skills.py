from __future__ import annotations

"""Marketing Skills & Copywriting Frameworks inspired by coreyhaines31/marketingskills (MIT License).

Provides specialized B2B outreach frameworks for high-converting 1-on-1 cold emails.
"""

FRAMEWORKS = {
    "PAS": {
        "name": "Problem-Agitate-Solve",
        "description": "Highlights the client's current pain point, briefly agitates the inefficiency, and offers a clean engineering solution.",
        "prompt_instruction": (
            "Use the PAS (Problem - Agitate - Solve) copywriting framework: "
            "1. State the lead's exact problem directly in sentence 1. "
            "2. Briefly agitate the time/cost waste of not solving it. "
            "3. Offer a clean, 1-on-1 engineering solution from your experience."
        ),
    },
    "BAB": {
        "name": "Before-After-Bridge",
        "description": "Paints the current manual state vs future automated state, bridging the gap with custom tech.",
        "prompt_instruction": (
            "Use the BAB (Before - After - Bridge) copywriting framework: "
            "1. Describe their current manual state (Before). "
            "2. Describe the automated/seamless future state (After). "
            "3. Offer your engineering solution as the bridge."
        ),
    },
    "DIRECT": {
        "name": "Direct Offer (Default)",
        "description": "Short, natural, 1-on-1 direct developer email under 75 words with zero fluff.",
        "prompt_instruction": (
            "Use a Direct 1-on-1 Developer approach: "
            "1. Reference their specific post/need in sentence 1. "
            "2. Mention a similar project built at TechNova World. "
            "3. End with a low-friction 5-minute chat request."
        ),
    },
}


def get_framework_instruction(framework_key: str = "DIRECT") -> str:
    """Returns the prompt instruction for the specified marketing framework."""
    key = framework_key.upper()
    return FRAMEWORKS.get(key, FRAMEWORKS["DIRECT"])["prompt_instruction"]
