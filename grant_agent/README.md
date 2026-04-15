# Grant Agent System

Automated grant discovery, qualification scoring, and AI-powered application generation.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2. Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Edit your business profile
# Open user_profile.json and fill in your details

# 4. Run the server
python main.py
```

Open http://localhost:8000 for the dashboard.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/grants | List grants (sorted by match score) |
| POST | /api/search | Live search Grants.gov |
| POST | /api/scan | Trigger background scan |
| POST | /api/grants/{id}/apply | Generate application with Claude AI |
| POST | /api/grants/{id}/checklist | Get step-by-step application guide |
| GET | /api/profile | View business profile |
| PUT | /api/profile | Update business profile |
| GET | /api/stats | Dashboard stats |
| GET | /docs | Interactive API docs (Swagger) |

## Architecture

```
grant_agent/
├── main.py                  # FastAPI app + startup
├── config.py                # Settings from .env
├── user_profile.json        # Your business profile (customize this)
├── requirements.txt
├── database/
│   └── db.py                # SQLite: upsert, query, score updates
├── discovery/
│   ├── grants_gov.py        # Grants.gov REST API v2
│   ├── rss_feeds.py         # RSS feed ingestion
│   ├── scraper.py           # Playwright dynamic scraper
│   └── normalizer.py        # Normalize all sources → standard schema
├── scoring/
│   └── scorer.py            # Rule-based scoring: match, win%, effort
├── generation/
│   └── generator.py         # Claude AI application generation
├── automation/
│   └── submitter.py         # Playwright form autofill
├── scheduler/
│   └── jobs.py              # APScheduler daily/weekly scans
├── api/
│   └── routes.py            # All FastAPI route handlers
└── dashboard/
    └── index.html           # Single-page dashboard UI
```

## Scoring System

Each grant receives:
- **Match Score (0–100)**: demographic fit + industry alignment + amount + deadline + location
- **Win Probability (0–90%)**: match score adjusted for competition level
- **Effort Level**: low / medium / high (based on grant requirements)
- **Days to Apply**: estimated prep time

## Customization

Edit `user_profile.json` to update your business profile — all scoring and application generation uses this.

Add new RSS feeds in `discovery/rss_feeds.py` → `RSS_SOURCES`.

Add new scrape targets in `discovery/scraper.py` → `SCRAPE_TARGETS`.

Adjust scoring weights in `scoring/scorer.py`.
