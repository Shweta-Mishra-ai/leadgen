from __future__ import annotations

import logging
import re
from typing import Any

from leadgen.config import Settings
from leadgen.report import _get_draft_client_and_model

logger = logging.getLogger("leadgen.reply_classifier")

CLASSIFIER_SYSTEM_PROMPT = """You are an expert sales inbox classifier. Analyze the client's email reply and classify their intent.

Allowed Classification Labels:
- CALL_REQUESTED (Client wants a phone/video meeting or call)
- INTERESTED (Client expresses interest, asks for pricing/portfolio)
- MORE_INFO (Client asks clarifying technical questions)
- NOT_INTERESTED (Client declines or unsubscribes)
- OUT_OF_OFFICE (Automated auto-responder)

Return ONLY a JSON object:
{"intent": "<LABEL>", "summary": "<1-sentence summary>"}
"""


def classify_email_reply(settings: Settings, reply_text: str) -> dict[str, Any]:
    """Classifies an incoming client email reply into intent categories."""
    reply_clean = reply_text.strip().lower()

    # Fast heuristic checks
    if any(phrase in reply_clean for phrase in ("out of office", "auto-reply", "automatic reply", "on vacation")):
        return {"intent": "OUT_OF_OFFICE", "summary": "Automated out-of-office responder."}

    if any(phrase in reply_clean for phrase in ("not interested", "unsubscribe", "remove me", "no thanks", "pass on this")):
        return {"intent": "NOT_INTERESTED", "summary": "Client declined opportunity."}

    if any(phrase in reply_clean for phrase in ("call", "schedule", "zoom", "meet", "calendar", "time to chat", "available on")):
        return {"intent": "CALL_REQUESTED", "summary": "Client requested a call/meeting."}

    client, model = _get_draft_client_and_model(settings)
    if not client:
        return {"intent": "INTERESTED", "summary": "Client sent a response."}

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Client Email Reply:\n{reply_text}"},
            ],
            timeout=20,
        )
        content = resp.choices[0].message.content or ""
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            import json
            data = json.loads(match.group(0))
            return {
                "intent": data.get("intent", "INTERESTED"),
                "summary": data.get("summary", "Client sent a response."),
            }
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM reply classification failed: %s", e)

    return {"intent": "INTERESTED", "summary": "Client sent a response."}
