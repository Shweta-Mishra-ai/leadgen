# leadgen

Multi-source freelance/client lead-generation pipeline for TechNova World.
Finds leads on X, Reddit, and the general web, scores them against your
niche, drafts short outreach notes for review, and delivers a daily Excel
report to Telegram. No server to host, no manual outreach automation —
runs entirely on GitHub Actions' free tier.

## Architecture

```
src/leadgen/
├── config.py              # pydantic Settings — validates env at startup
├── models.py               # RawLead / ScoredLead — validation boundary
├── storage.py               # SQLite: dedup, indexed queries, transactions
├── pipeline.py               # orchestrator: concurrent sources, scoring
├── report.py                   # drafts notes, builds Excel
├── notify.py                    # Telegram delivery
├── sources/
│   ├── base.py                    # shared retry + circuit-breaker + isolation
│   ├── grok.py                     # X + Reddit via xAI's x_search/web_search
│   ├── gemini.py                    # free Google Search grounding
│   ├── tavily_source.py              # free structured search (web + reddit.com)
│   ├── apify_source.py                # X/Twitter search via scraper Actor (needs dedicated account)
│   ├── reddit_source.py                # official Reddit API (optional)
│   └── duckduckgo_source.py            # free, no-key backup source
├── run_pipeline_cli.py       # entrypoint: leadgen-run
└── generate_report_cli.py    # entrypoint: leadgen-report
tests/                       # 24 tests, pytest + mocks, no live API calls
.github/workflows/
├── ci.yml                  # lint (ruff) + test on every push/PR
└── daily-pipeline.yml       # scheduled run, 10 AM IST daily
```

### Why it's built this way

- **Every source is independent and optional.** Add keys as you get them
  (Reddit's approval, OpenRouter, etc.) — nothing else changes.
- **Concurrent fetching with a hard timeout per source** (`pipeline.py`),
  so one slow API never stalls the whole run.
- **Retry with exponential backoff, but only on transient errors**
  (`sources/base.py`) — a bad API key fails once, loud, instead of
  retrying the same failure 3 times and burning quota.
- **Circuit breaker per source**: 3 consecutive failed topics and a
  source stops being hammered for the rest of that run.
- **Validation at the boundary** (`models.py`): every row from every
  source passes through `RawLead.model_validate()` before it can touch
  scoring or storage. Malformed rows are dropped and logged, not
  silently corrupting downstream data.
- **SQLite instead of flat files** for dedup: atomic, race-safe UNIQUE
  constraint on URL hash instead of read-modify-write on a text file.
- **Nothing is sent to anyone automatically.** The pipeline finds and
  scores leads; the report drafts notes for your review. Sending stays
  a manual, deliberate step — see "What's NOT automated" below.

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env   # fill in whichever keys you have — rest auto-skip
leadgen-run             # fetch + score + store leads
leadgen-report           # draft notes, build Excel, send to Telegram
```

Recommended starting keys, cheapest first:
- **Tavily** (free, 1,000 credits/mo, no card) — covers general web + Reddit
- **Gemini** (free, 5,000 grounded searches/mo, no card) — covers general web
- **Groq** (free, 14,400 req/day, no card) — ⚠️ NOT the same as Grok/xAI,
  despite the name. console.groq.com hosts fast open-model inference (Llama,
  etc.) with no live web/X search — used here only as a free drafting model.
- **Grok/xAI** (console.x.ai, ~$5/1000 calls) — the ONLY source with real
  X/Twitter access; also usable for drafting if you have it
- **Apify** (free, $5/mo credit, no card) — X/Twitter search via a scraper
  Actor, fits free tier at default settings (~$4.20/mo). ⚠️ Requires a
  DEDICATED X account's session cookies, not your personal account — see
  the warning in `sources/apify_source.py` and `.env.example`
- **OpenRouter** (optional) — last-resort drafting fallback if neither
  Grok nor Groq is set
- **Reddit official API** (free, 2-4wk approval) — add once approved; Tavily's
  reddit.com-scoped search covers you reasonably well in the meantime

## Testing

```bash
pytest --cov=leadgen --cov-report=term-missing
ruff check src tests
```

24 tests cover: config validation, model validation (rejects malformed
URLs/scores), storage dedup + transactions, source retry/circuit-breaker/
isolation (via a `FlakySource` test double — no live API calls), and
pipeline-level resilience (one source crashing doesn't take down others).

## Deploying (no server needed)

1. Push this repo to GitHub
2. Add repo Secrets: `XAI_API_KEY`, `GEMINI_API_KEY`, `REDDIT_CLIENT_ID`,
   `REDDIT_CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   (all optional — add what you have, the rest stay skipped)
3. `daily-pipeline.yml` runs automatically at 10 AM IST, or trigger it
   manually from the Actions tab

## What's NOT automated (on purpose)

- No auto-DM, no auto-comment, no auto-posting to Reddit/X. Reddit's
  Responsible Builder Policy requires consent before private messages and
  bans automated spam via posts/comments/DMs — violating this gets
  accounts banned fast, and burns the leads this pipeline just found.
- Outreach drafts are for your review, not auto-send. Cold email has its
  own real rules (sender ID, working unsubscribe) worth a human pass.

## Adding a new source

1. Subclass `LeadSource` in `sources/`, implement `is_configured()` and
   `_fetch_topic()`
2. Register it in `sources/__init__.py` and `pipeline.build_sources()`
3. Add a `FlakySource`-style test in `tests/test_sources.py` covering at
   least one failure path
