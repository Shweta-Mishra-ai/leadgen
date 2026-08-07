from __future__ import annotations

import logging
from datetime import UTC, datetime

import pandas as pd

from leadgen.config import Settings
from leadgen.notify import send_telegram_file
from leadgen.storage import LeadStore

logger = logging.getLogger("leadgen.report")

DRAFT_PROMPT = """Write a short (under 60 words), non-salesy outreach note
for a freelance GenAI/AI-automation engineer to send in reply to this lead.
Reference their specific need, don't be generic, no exclamation marks,
no "I hope this finds you well" filler.

Lead title: {title}
Lead snippet: {snippet}

Return ONLY the note text, nothing else.
"""


def draft_note(client, model: str, title: str, snippet: str) -> str:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": DRAFT_PROMPT.format(title=title, snippet=snippet)}],
        )
        return resp.choices[0].message.content
    except Exception as e:  # noqa: BLE001 - a failed draft shouldn't kill the whole report
        logger.warning("draft generation failed: %s", e)
        return "[draft unavailable — write manually]"


def _get_draft_client_and_model(settings: Settings):
    """Priority: Grok/xAI (already used for search, one less key to manage)
    -> Groq (free tier is genuinely generous: 14,400 req/day, no card, but
    NOT the same product as Grok/xAI — no web/X search, drafting only)
    -> OpenRouter (fallback; free models there are less consistently
    available). Returns (None, None) if none configured — drafting skipped."""
    from openai import OpenAI

    if settings.xai_api_key:
        return OpenAI(api_key=settings.xai_api_key, base_url="https://api.x.ai/v1"), settings.xai_model
    if settings.groq_api_key:
        return (
            OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1"),
            settings.groq_model,
        )
    if settings.openrouter_api_key:
        headers = {
            "HTTP-Referer": "https://github.com/Shweta-Mishra-ai/leadgen",
            "X-Title": "leadgen",
        }
        return (
            OpenAI(
                api_key=settings.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers=headers,
            ),
            settings.openrouter_model,
        )
    return None, None


def generate_report(settings: Settings, store: LeadStore) -> str:
    all_leads = store.all_leads()
    if not all_leads:
        logger.warning("no leads in store, nothing to report")
        raise ValueError("No leads found — run the pipeline first")

    df = pd.DataFrame(all_leads)

    drafts = []
    client, model = _get_draft_client_and_model(settings)
    if client:
        top = store.top_leads(limit=settings.top_n_for_drafts)
        for lead in top:
            note = draft_note(client, model, lead["title"], lead["snippet"])
            drafts.append({
                "title": lead["title"], "url": lead["url"], "source": lead["source"],
                "score": lead["score"], "draft_note": note,
            })
    else:
        logger.info("No drafting keys configured (XAI, GROQ, or OPENROUTER), skipping draft generation")

    drafts_df = pd.DataFrame(drafts) if drafts else pd.DataFrame(
        columns=["title", "url", "source", "score", "draft_note"]
    )

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    report_path = f"leads_report_{today}.xlsx"
    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Leads", index=False)
        drafts_df.to_excel(writer, sheet_name="Drafts", index=False)

    send_telegram_file(
        settings.telegram_bot_token, settings.telegram_chat_id, report_path,
        caption=f"Daily leads report — {len(df)} total leads, {len(drafts_df)} drafted for review.",
    )
    return report_path
