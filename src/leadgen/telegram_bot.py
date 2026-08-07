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
                "• <b>/super &lt;lead_id&gt; [PAS/BAB/DIRECT]</b> — Multi-role Super Agent (Profile ➔ Copywrite ➔ Audit ➔ Deliver)\n"
                "• <b>/autoemail &lt;lead_id&gt;</b> — Auto-find contact email & send humanized Gmail outreach\n"
                "• <b>/email &lt;lead_id&gt; &lt;recipient_email&gt;</b> — Send humanized, 1-on-1 personalized Gmail outreach\n"
                "• <b>/classify &lt;reply_text&gt;</b> — Classify incoming email reply intent\n"
                "• <b>/followup</b> — Process automated follow-up drip sequence\n"
                "• <b>/search &lt;keyword&gt;</b> — Instant web search for leads\n"
                "• <b>/outreach</b> — View outreach history & analytics\n"
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
                    f"   🔗 <b>URL:</b> {url}\n"
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
                    f"   🔗 <b>URL:</b> {lead.url}\n"
                )

            send_telegram_message(self.bot_token, str(chat_id), "\n".join(lines), parse_mode="HTML")

        elif command == "/outreach":
            logs = self.store.all_outreach_logs()
            if not logs:
                send_telegram_message(self.bot_token, str(chat_id), "No direct outreach emails sent yet.")
                return
            lines = [f"📧 <b>Direct Outreach History ({len(logs)} total)</b>", ""]
            for idx, log in enumerate(logs[:5], 1):
                lines.append(
                    f"{idx}. <b>To:</b> {html.escape(log['recipient_email'])}\n"
                    f"   <b>Subject:</b> {html.escape(log['subject'])}\n"
                    f"   <b>Status:</b> <code>{log['status']}</code> | <i>{log['sent_at'][:10]}</i>\n"
                )
            send_telegram_message(self.bot_token, str(chat_id), "\n".join(lines), parse_mode="HTML")

        elif command == "/classify":
            if not args:
                send_telegram_message(
                    self.bot_token,
                    str(chat_id),
                    "⚠️ Usage: <code>/classify &lt;client reply text&gt;</code>",
                    parse_mode="HTML",
                )
                return

            from leadgen.reply_classifier import classify_email_reply
            res = classify_email_reply(self.settings, args)
            intent = res.get("intent", "INTERESTED")
            summary = res.get("summary", "")

            msg = (
                f"🧠 <b>Client Email Intent Classified</b>\n\n"
                f"<b>Intent Label:</b> <code>{intent}</code>\n"
                f"<b>Summary:</b> {html.escape(summary)}"
            )
            send_telegram_message(self.bot_token, str(chat_id), msg, parse_mode="HTML")

        elif command == "/followup":
            send_telegram_message(
                self.bot_token,
                str(chat_id),
                "🔄 Running 3-stage follow-up drip (Day 3 → Day 7 → Day 14)...",
            )
            from leadgen.followup import process_pending_followups
            results = process_pending_followups(self.settings, self.store)
            total = sum(results.values())
            msg = (
                f"✅ <b>Follow-Up Drip Complete!</b>\n\n"
                f"📅 <b>Day 3  (Stage 1):</b> {results.get('stage_1', 0)} sent\n"
                f"📅 <b>Day 7  (Stage 2):</b> {results.get('stage_2', 0)} sent\n"
                f"📅 <b>Day 14 (Stage 3):</b> {results.get('stage_3', 0)} sent\n\n"
                f"<b>Total:</b> {total} follow-up email(s) sent."
            )
            send_telegram_message(self.bot_token, str(chat_id), msg, parse_mode="HTML")

        elif command == "/super":
            args_list = args.split()
            if not args_list:
                send_telegram_message(
                    self.bot_token,
                    str(chat_id),
                    "⚠️ Usage: <code>/super &lt;lead_id&gt; [PAS/BAB/DIRECT]</code>\nExample: <code>/super 1 PAS</code>",
                    parse_mode="HTML",
                )
                return

            try:
                lead_id = int(args_list[0])
            except ValueError:
                send_telegram_message(self.bot_token, str(chat_id), "❌ Invalid lead_id format.")
                return

            framework = args_list[1].upper() if len(args_list) > 1 else "PAS"

            lead = self.store.get_lead_by_id(lead_id)
            if not lead:
                send_telegram_message(self.bot_token, str(chat_id), f"❌ Lead ID {lead_id} not found.")
                return

            send_telegram_message(
                self.bot_token,
                str(chat_id),
                f"🤖 <b>Super Agent Multi-Role Pipeline Executing...</b>\n\n"
                f"• Role 1 (Profiler): Analyzing lead intent\n"
                f"• Role 2 (Copywriter): Framework <code>{framework}</code>\n"
                f"• Role 3 (Humanizer Audit): Stripping AI filler & links\n"
                f"• Role 4 (Deliverability): Checking email & SMTP",
                parse_mode="HTML",
            )

            from leadgen.super_agent import SuperOutreachAgent
            super_agent = SuperOutreachAgent(self.settings, self.store)
            res = super_agent.process_lead(
                title=lead["title"],
                snippet=lead["snippet"],
                url=lead["url"],
                framework=framework,
            )

            target = res["target_email"]
            subj = res["subject"]
            body = res["body"]
            sent = res["sent"]

            if sent:
                msg = (
                    f"✅ <b>Super Agent Outreach Delivered!</b>\n\n"
                    f"<b>To:</b> {target}\n"
                    f"<b>Framework:</b> <code>{framework}</code>\n"
                    f"<b>Subject:</b> {html.escape(str(subj))}\n\n"
                    f"<b>Body:</b>\n{html.escape(str(body))}"
                )
            else:
                msg = (
                    f"📝 <b>Super Agent Output Generated (Not Sent)</b>\n\n"
                    f"<b>Target Email:</b> {target}\n"
                    f"<b>Framework:</b> <code>{framework}</code>\n"
                    f"<b>Subject:</b> {html.escape(str(subj))}\n\n"
                    f"<b>Body:</b>\n{html.escape(str(body))}"
                )

            send_telegram_message(self.bot_token, str(chat_id), msg, parse_mode="HTML")

        elif command == "/autoemail":
            if not args:
                send_telegram_message(
                    self.bot_token,
                    str(chat_id),
                    "⚠️ Usage: <code>/autoemail &lt;lead_id&gt;</code>\nExample: <code>/autoemail 1</code>",
                    parse_mode="HTML",
                )
                return

            try:
                lead_id = int(args.split()[0])
            except ValueError:
                send_telegram_message(self.bot_token, str(chat_id), "❌ Invalid lead_id format.")
                return

            lead = self.store.get_lead_by_id(lead_id)
            if not lead:
                send_telegram_message(self.bot_token, str(chat_id), f"❌ Lead ID {lead_id} not found.")
                return

            send_telegram_message(
                self.bot_token,
                str(chat_id),
                f"🔎 Searching contact email for lead #{lead_id}...",
            )
            from leadgen.email_finder import find_contact_email_for_lead
            found_email = find_contact_email_for_lead(lead["title"], lead["url"], lead["snippet"])

            if not found_email:
                send_telegram_message(
                    self.bot_token,
                    str(chat_id),
                    f"⚠️ Could not automatically discover email for lead #{lead_id}.\nPlease specify email using: <code>/email {lead_id} &lt;client@domain.com&gt;</code>",
                    parse_mode="HTML",
                )
                return

            send_telegram_message(
                self.bot_token,
                str(chat_id),
                f"📧 Found contact email: <code>{found_email}</code>. Generating humanized email...",
                parse_mode="HTML",
            )
            from leadgen.email_sender import send_email
            from leadgen.humanizer import generate_humanized_email

            subj, body = generate_humanized_email(self.settings, lead["title"], lead["snippet"])

            if not self.settings.gmail_address or not self.settings.gmail_app_password:
                msg = (
                    f"📝 <b>Humanized Outreach Generated (Not Sent — Gmail Credentials Missing)</b>\n\n"
                    f"<b>Discovered To:</b> {found_email}\n"
                    f"<b>Subject:</b> {html.escape(subj)}\n\n"
                    f"<b>Body:</b>\n{html.escape(body)}\n\n"
                    f"<i>Add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to enable direct sending.</i>"
                )
                send_telegram_message(self.bot_token, str(chat_id), msg, parse_mode="HTML")
                return

            success = send_email(self.settings, found_email, subj, body)
            if success:
                self.store.log_outreach(lead["url"], found_email, subj, body, status="sent")
                send_telegram_message(
                    self.bot_token,
                    str(chat_id),
                    f"✅ <b>Auto Outreach Sent!</b>\n\n<b>To:</b> {found_email}\n<b>Subject:</b> {html.escape(subj)}",
                    parse_mode="HTML",
                )
            else:
                self.store.log_outreach(lead["url"], found_email, subj, body, status="failed")
                send_telegram_message(
                    self.bot_token, str(chat_id), f"❌ Failed to send email to {found_email}."
                )

        elif command == "/email":
            args_list = args.split()
            if len(args_list) < 2:
                send_telegram_message(
                    self.bot_token,
                    str(chat_id),
                    "⚠️ Usage: <code>/email &lt;lead_id&gt; &lt;recipient_email&gt;</code>\nExample: <code>/email 1 client@company.com</code>",
                    parse_mode="HTML",
                )
                return

            try:
                lead_id = int(args_list[0])
                to_email = args_list[1]
            except ValueError:
                send_telegram_message(self.bot_token, str(chat_id), "❌ Invalid lead_id format.")
                return

            lead = self.store.get_lead_by_id(lead_id)
            if not lead:
                send_telegram_message(self.bot_token, str(chat_id), f"❌ Lead ID {lead_id} not found.")
                return

            send_telegram_message(
                self.bot_token,
                str(chat_id),
                f"🧠 Generating humanized, non-AI proposal note for lead #{lead_id}...",
            )

            from leadgen.email_sender import send_email
            from leadgen.humanizer import generate_humanized_email

            subj, body = generate_humanized_email(self.settings, lead["title"], lead["snippet"])

            if not self.settings.gmail_address or not self.settings.gmail_app_password:
                msg = (
                    f"📝 <b>Humanized Outreach Generated (Not Sent — Gmail Credentials Missing)</b>\n\n"
                    f"<b>To:</b> {to_email}\n"
                    f"<b>Subject:</b> {html.escape(subj)}\n\n"
                    f"<b>Body:</b>\n{html.escape(body)}\n\n"
                    f"<i>Add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to enable direct sending.</i>"
                )
                send_telegram_message(self.bot_token, str(chat_id), msg, parse_mode="HTML")
                return

            success = send_email(self.settings, to_email, subj, body)
            if success:
                self.store.log_outreach(lead["url"], to_email, subj, body, status="sent")
                send_telegram_message(
                    self.bot_token,
                    str(chat_id),
                    f"✅ <b>Outreach Sent Successfully!</b>\n\n<b>To:</b> {to_email}\n<b>Subject:</b> {html.escape(subj)}",
                    parse_mode="HTML",
                )
            else:
                self.store.log_outreach(lead["url"], to_email, subj, body, status="failed")
                send_telegram_message(
                    self.bot_token, str(chat_id), f"❌ Failed to send email to {to_email}."
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
