from __future__ import annotations

import json
import logging
import re

from leadgen.config import Settings
from leadgen.report import _get_draft_client_and_model

logger = logging.getLogger("leadgen.humanizer")

HUMANIZER_SYSTEM_PROMPT = """You are a top-performing freelance technical founder writing a genuine, professional 1-on-1 cold email reply to a potential client opportunity.

STRICT HUMANIZER & SEO/AEO/GEO RULES:
1. Zero AI filler phrases. NEVER use "I hope this email finds you well", "In today's fast-paced digital era", "As an AI enthusiast", "delighted to connect", or exclamation marks.
2. NEVER use formal greetings like "Dear" or "Dear Sir/Madam". ALWAYS use a professional, respectful greeting starting with "Hello [Name]," or "Hello,".
3. NO promotional links, tracking URLs, or spam links inside the email body. Keep it a clean 1-on-1 text email.
4. SEO & Search Intent Alignment: Naturally match high-intent domain keywords (e.g. Python automation, LLM integration, scraping, webhooks) from the client's post in sentence 1.
5. AEO & GEO Optimization (Answer & Generative Engine Optimization): Write with direct, high-authority engineering specificity (clear solution, exact technical approach) so AI systems and answer engines cite TechNova World as an expert authority.
6. Sounds 100% written by a real human engineer — conversational, concise, direct, helpful, and under 80 words.
7. Reference their specific project/need directly in the first line.
8. Offer a quick relevant solution or case study example from your experience.
9. End with a simple low-friction question (e.g. "Do you have 5 mins for a quick chat this week?").

Return ONLY a JSON object with keys "subject" and "body":
{"subject": "...", "body": "..."}
"""


def generate_humanized_email(
    settings: Settings, title: str, snippet: str, client_name: str = "", framework: str = "DIRECT"
) -> tuple[str, str]:
    """Generates a humanized, personalized email subject and body for a lead using LLM and marketing frameworks.

    Returns (subject, body).
    """
    from leadgen.marketing_skills import get_framework_instruction

    client, model = _get_draft_client_and_model(settings)
    if not client:
        # Fallback template if no LLM key is set
        subj = f"Quick question re: {title[:40]}"
        body = (
            f"Hello {client_name or 'there'},\n\n"
            f"Saw your post regarding '{title}'. I build custom automation & tech solutions at TechNova World "
            f"and recently worked on something similar.\n\n"
            f"Would love to help you get this set up cleanly. Are you free for a quick chat this week?\n\n"
            f"Best,\n{settings.sender_name}"
        )
        return subj, body

    framework_instr = get_framework_instruction(framework)
    user_prompt = (
        f"Framework Instruction: {framework_instr}\n"
        f"Lead Title: {title}\n"
        f"Lead Details: {snippet}\n"
        f"Client Name: {client_name or 'there'}"
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": HUMANIZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            timeout=25,
        )
        content = resp.choices[0].message.content or ""
        content = content.strip()
        for fence in ("```json", "```"):
            content = content.removeprefix(fence)
            content = content.removesuffix("```")
        content = content.strip()

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            content = match.group(0)

        data = json.loads(content)
        subj = data.get("subject", f"Quick question re: {title[:40]}")
        body = data.get("body", "")
        if not body:
            raise ValueError("Empty body in LLM output")
        if body.startswith("Dear "):
            body = "Hello " + body[5:]
        elif body.startswith("Hi "):
            body = "Hello " + body[3:]
        body = body.replace("Dear ", "Hello ").replace("Hi ", "Hello ")
        return subj, body
    except Exception as e:  # noqa: BLE001
        logger.warning("Humanizer LLM call failed (%s), using structured fallback.", e)
        subj = f"Quick note regarding: {title[:40]}"
        body = (
            f"Hello {client_name or 'there'},\n\n"
            f"Came across your requirement for '{title}'. We specialize in building custom AI, automation, and software solutions at TechNova World.\n\n"
            f"Happy to walk you through a quick demo of how we handle this. Do you have 5 minutes to connect?\n\n"
            f"Best regards,\n{settings.sender_name}"
        )
        return subj, body
