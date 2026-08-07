from __future__ import annotations

import html
import logging
import time

import requests

from leadgen.config import Settings
from leadgen.notify import send_telegram_message
from leadgen.pipeline import score_lead
from leadgen.sources import DuckDuckGoSource
from leadgen.storage import LeadStore

logger = logging.getLogger("leadgen.telegram_bot")


class TelegramBot:
    def __init__(self, settings: Settings, store: LeadStore):
        self.settings = settings
        self.store = store
        self.bot_token = settings.telegram_bot_token
        self.offset = 0

    def is_configured(self) -> bool:
        return bool(self.bot_token)

    def handle_command(self, chat_id: str, text: str) -> None:
        text = text.strip()
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command in ("/start", "/help"):
            msg = (
                "🤖 <b>LeadGen Interactive Telegram Bot</b>\n\n"
                "Available Commands:\n"
                "• <b>/search &lt;keyword&gt;</b> — Instant web search for leads (e.g. <code>/search python analyst</code>)\n"
                "• <b>/stats</b> — View lead database statistics category-wise\n"
                "• <b>/top</b> — Get top 5 highest scored leads\n"
                "• <b>/report</b> — Generate and send full Excel report\n"
                "• <b>/help</b> — Show this help message"
            )
            send_telegram_message(self.bot_token, str(chat_id), msg, parse_mode="HTML")

        elif command == "/stats":
            total = self.store.count()
            all_leads = self.store.all_leads()
            sources_cnt: dict[str, int] = {}
            for item in all_leads:
                src = item.get("source", "unknown")
                sources_cnt[src] = sources_cnt.get(src, 0) + 1

            lines = ["📊 <b>LeadGen Database Statistics</b>", f"<b>Total Stored Leads:</b> {total}", ""]
            lines.append("<b>By Source:</b>")
            for src, count in sources_cnt.items():
                lines.append(f"• <code>{src}</code>: {count}")

            send_telegram_message(self.bot_token, str(chat_id), "\n".join(lines), parse_mode="HTML")

        elif command == "/top":
            top_leads = self.store.top_leads(limit=5)
            if not top_leads:
                send_telegram_message(self.bot_token, str(chat_id), "No leads found in database.")
                return

            lines = ["🌟 <b>Top 5 High-Score Leads:</b>", ""]
            for idx, lead in enumerate(top_leads, 1):
                title = html.escape(lead.get("title", ""))
                score = lead.get("score", 0)
                url = lead.get("url", "")
                src = lead.get("source", "")
                lines.append(
                    f"{idx}. <b>{title}</b>\n"
                    f"   ⭐ Score: <code>{score}</code> | Source: <i>{src}</i>\n"
                    f"   🔗 <a href=\"{url}\">Open Lead Link</a>\n"
                )
            send_telegram_message(self.bot_token, str(chat_id), "\n".join(lines), parse_mode="HTML")

        elif command == "/search":
            if not args:
                send_telegram_message(
                    self.bot_token, str(chat_id), "⚠️ Please specify a keyword. Example: <code>/search python analyst</code>"
                )
                return

            send_telegram_message(
                self.bot_token, str(chat_id), f"🔎 Searching live leads for <b>{html.escape(args)}</b>..."
            )
            ddg = DuckDuckGoSource(max_retries=1, timeout_seconds=15)
            raw = ddg.fetch_all([args])
            from leadgen.models import ScoredLead
            scored = [ScoredLead.from_raw(r, score_lead(r)) for r in raw]
            scored = [s for s in scored if s.score > 0]
            new_inserted = self.store.insert_new(scored)

            if not scored:
                send_telegram_message(
                    self.bot_token, str(chat_id), f"No high-relevance leads found for '<b>{html.escape(args)}</b>'."
                )
                return

            scored_sorted = sorted(scored, key=lambda s: s.score, reverse=True)[:5]
            lines = [
                f"🔎 <b>Search Results for '{html.escape(args)}'</b>",
                f"Found {len(scored)} relevant leads ({new_inserted} new saved to database).",
                "",
                "<b>Top Results:</b>",
            ]
            for idx, lead in enumerate(scored_sorted, 1):
                lines.append(
                    f"{idx}. <b>{html.escape(lead.title)}</b>\n"
                    f"   ⭐ Score: <code>{lead.score}</code>\n"
                    f"   🔗 <a href=\"{lead.url}\">Open Link</a>\n"
                )

            send_telegram_message(self.bot_token, str(chat_id), "\n".join(lines), parse_mode="HTML")

        elif command == "/report":
            send_telegram_message(self.bot_token, str(chat_id), "⏳ Generating full Excel report...")
            from leadgen.report import generate_report
            try:
                report_path = generate_report(self.settings, self.store)
                send_telegram_message(
                    self.bot_token, str(chat_id), f"✅ Report generated: <code>{report_path}</code>"
                )
            except Exception as e:  # noqa: BLE001
                send_telegram_message(
                    self.bot_token, str(chat_id), f"❌ Report generation failed: {e}"
                )

        else:
            send_telegram_message(
                self.bot_token,
                str(chat_id),
                "Unknown command. Type <b>/help</b> for a list of available commands.",
            )

    def process_updates(self) -> int:
        if not self.is_configured():
            logger.warning("Telegram Bot token missing, cannot poll updates.")
            return 0

        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        try:
            resp = requests.get(url, params={"offset": self.offset, "timeout": 5}, timeout=10)
            if resp.status_code != 200:
                return 0
            data = resp.json()
            updates = data.get("result", [])
            for update in updates:
                self.offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                if text and chat_id:
                    self.handle_command(str(chat_id), text)
            return len(updates)
        except Exception as e:  # noqa: BLE001
            logger.error("Error polling Telegram updates: %s", e)
            return 0

    def run_polling(self) -> None:
        logger.info("Telegram Bot started long polling...")
        while True:
            self.process_updates()
            time.sleep(2)
