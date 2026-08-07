# LeadGen - Multi-Category Client Lead Generation Pipeline & Telegram Bot

An enterprise-grade, multi-source freelance and client lead generation pipeline designed for high-value client acquisition. 

Finds live client leads across **5 core categories** (Automation, Freelance Writing, Data Analysis & Engineering, App Development & Sales, and AI/GenAI), scores leads against genuine hiring intent, filters out web noise/listicles, generates AI outreach drafts, formats reports with clickable Excel hyperlinks, and delivers daily interactive summaries to Telegram.

---

## 🌟 Key Features

- **5 Target Lead Categories**:
  1. ⚡ **Workflow & Process Automation**: n8n, Zapier, Make.com, Python scripts, web scrapers.
  2. ✍️ **Freelance Writing & Copywriting**: Technical writing, API docs, copywriting, content marketing.
  3. 📊 **Data Analysis & Engineering**: Python data science, SQL analytics, Power BI, Snowflake.
  4. 📱 **App Sales & Development**: Mobile app building (React Native, Flutter), SaaS web apps, custom software contracts.
  5. 🤖 **AI & GenAI Engineering**: RAG pipelines, LLM token optimization, AI agent development.
- **Robust API Integrations**:
  - **Google Gemini**: Uses free Google Search grounding with `gemini-2.5-flash`.
  - **xAI / Grok**: Leverages `grok-2-latest` for live X (Twitter) search and drafting.
  - **OpenRouter & Groq**: Fallback AI drafting models.
  - **Tavily**: Structured search across general web & `reddit.com`.
  - **Apify**: Community X/Twitter scraper Actor support.
  - **Reddit & DuckDuckGo**: Official/Public Reddit scrapers & no-key fallback search.
- **Noise & Quality Filtering**:
  - Automatically filters out listicles, course ads, blog posts, and job aggregators (`NOISE_DOMAINS`).
  - Rewards genuine hiring signals (`HIRING_SIGNAL_KEYWORDS`).
- **Rich Excel & Telegram Formatting**:
  - **Excel (`.xlsx`)**: Styled dark headers (`#1E293B`), auto-fitted column widths, text wrapping, and **clickable `=HYPERLINK()` Excel formulas**.
  - **Telegram**: Sends rich HTML summary messages with direct clickable top lead links alongside formatted Excel attachments.
- **Interactive Telegram Bot (`leadgen-bot`)**:
  - Native long-polling bot supporting `/search <keyword>`, `/stats`, `/top`, `/report`, and `/help` without external platform dependencies.

---

## 🏗️ Architecture

```text
src/leadgen/
├── config.py              # Pydantic Settings — validates environment & keys at startup
├── models.py               # RawLead / ScoredLead — validation boundary
├── storage.py               # SQLite: dedup, indexed queries, transaction safety
├── pipeline.py               # Orchestrator: concurrent sources, multi-category scoring
├── report.py                   # Drafts notes, builds styled Excel, sends Telegram HTML
├── notify.py                    # Telegram messaging & file delivery API
├── telegram_bot.py              # Interactive Telegram command handler (/search, /stats, /top)
├── telegram_bot_cli.py          # Entrypoint: leadgen-bot
├── sources/
│   ├── base.py                    # Shared retry + circuit-breaker + isolation
│   ├── grok.py                     # xAI / Grok search (grok-2-latest)
│   ├── gemini.py                    # Google Gemini search (gemini-2.5-flash)
│   ├── tavily_source.py              # Structured web & reddit search
│   ├── apify_source.py                # X/Twitter search via scraper Actor
│   ├── reddit_source.py                # Official Reddit PRAW API
│   ├── reddit_public_source.py         # Public Reddit JSON endpoint
│   └── duckduckgo_source.py            # Free backup search engine
├── run_pipeline_cli.py       # Entrypoint: leadgen-run
└── generate_report_cli.py    # Entrypoint: leadgen-report

tests/                       # Comprehensive pytest suite (67+ tests)
.github/workflows/
├── ci.yml                  # Linting (ruff) + unit testing on push/PR
└── daily-pipeline.yml       # Scheduled daily run (10:00 AM IST)
```

---

## ⚡ Quick Start

### 1. Installation
```bash
pip install -e ".[dev]"
```

### 2. Environment Configuration
Copy `.env.example` to `.env` and fill in whichever keys you have (all sources are modular & auto-skip unconfigured keys):
```bash
cp .env.example .env
```

### 3. CLI Commands

```bash
# Fetch, score, and store new leads across all categories
leadgen-run

# Generate styled Excel report & deliver summary to Telegram
leadgen-report

# Start interactive Telegram Bot listener (/search, /stats, /top, /report)
leadgen-bot
```

---

## 🤖 Interactive Telegram Bot Usage

When `TELEGRAM_BOT_TOKEN` is set, run `leadgen-bot` to enable Telegram command processing:

| Command | Action |
| :--- | :--- |
| `/search <keyword>` | Performs instant live web search for leads (e.g. `/search python analyst`) and replies in chat |
| `/top` | Displays top 5 highest scored leads with direct clickable links |
| `/stats` | Shows lead database statistics and count per category |
| `/report` | Generates and sends updated Excel report on demand |
| `/help` | Lists all available bot commands |

---

## 🧪 Testing & CI Cleanliness

Run lint checks and complete unit test coverage:
```bash
# Run linter
ruff check src tests

# Run unit tests with coverage report
pytest --cov=leadgen --cov-report=term-missing
```

---

## 🚀 GitHub Actions Deployment

The repository includes a automated GitHub Action workflow (`.github/workflows/daily-pipeline.yml`):
- Runs automatically at **10:00 AM IST** daily (or trigger manually via `Workflow Dispatch` in GitHub Actions tab).
- Fetches leads, generates the styled Excel report, and pushes notifications directly to your Telegram bot.

---

## 📄 License
MIT License. Developed for TechNova World.
