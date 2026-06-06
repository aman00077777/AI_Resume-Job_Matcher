# AI Resume-Job Matching Application

An end-to-end AI-powered system that monitors company career pages, evaluates job-candidate fit using Gemini AI, and sends Discord alerts when strong matches are found.

## How It Works

```
Resume (PDF)                    Career Page URLs
     |                                |
     v                                v
 PyPDF2 text extraction       Firecrawl scraping
     |                                |
     v                                v
 Gemini structures resume      Job listings extracted
     |                                |
     +----------+   +-----------+-----+
                |   |
                v   v
        Gemini Match Scoring
        (weighted 0-100%)
                |
         +------+------+
         |             |
    score >= 80    score < 80
         |             |
    Discord Alert   Stored for
    + stored        dashboard view
```

## Features

- **Resume Parsing** — Upload PDF, AI extracts skills, experience, education
- **Smart Scraping** — Firecrawl handles JavaScript-heavy career pages
- **AI Matching** — Gemini evaluates fit across 4 weighted criteria
- **Discord Alerts** — Instant notifications for strong matches (80%+)
- **Streamlit Dashboard** — Manage sources, view matches, export to CSV
- **Scheduled Runs** — GitHub Actions triggers scraping every 6 hours
- **Multi-user** — Supabase Auth with per-user data isolation

## Match Scoring

| Criterion | Weight | What It Measures |
|-----------|--------|------------------|
| Skills Overlap | 35% | Technical skills match |
| Experience Level | 25% | Years + depth of experience |
| Job Title Relevance | 25% | Career trajectory alignment |
| Location Preference | 15% | Geographic / remote compatibility |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend API | FastAPI + Python 3.11 |
| AI Scraping | Firecrawl API |
| AI Matching | Gemini 1.5 Flash (Google) |
| Database | Supabase (PostgreSQL) |
| Dashboard | Streamlit |
| Auth | Supabase Auth (JWT) |
| Alerts | Discord Webhooks |
| Scheduling | GitHub Actions (cron) |
| Deployment | Render (API + Dashboard) |

## Live Demo

- **Dashboard:** https://ai-resume-job-matcher-1-b78v.onrender.com
- **API:** https://ai-resume-job-matcher-bazm.onrender.com
- **API Docs:** https://ai-resume-job-matcher-bazm.onrender.com/docs

## Prerequisites

- Python 3.10+
- [Supabase account](https://supabase.com) (free tier)
- [Google Gemini API key](https://aistudio.google.com) (free tier)
- [Firecrawl API key](https://www.firecrawl.dev) (optional)
- [Discord webhook URL](https://support.discord.com/hc/en-us/articles/228383668) (optional)

## Quick Start (Local Development)

### 1. Clone and install

```bash
git clone https://github.com/aman00077777/AI_Resume-Job_Matcher.git
cd AI_Resume-Job_Matcher
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-public-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

GEMINI_API_KEY=your-gemini-api-key

FIRECRAWL_API_KEY=your-firecrawl-key
DISCORD_WEBHOOK_URL=

MATCH_THRESHOLD=80
SCRAPE_MAX_JOBS_PER_SOURCE=50
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
API_BASE_URL=http://localhost:8000
SERVICE_API_KEY=your-service-key
```

### 3. Set up Supabase database

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** in your dashboard
3. Copy and paste the contents of `sql/schema.sql`
4. Click **Run** to create all tables
5. Copy your project URL and keys from **Settings > API**

### 4. Configure Streamlit secrets

Create `.streamlit/secrets.toml`:

```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_KEY = "your-anon-public-key"
```

### 5. Run the API

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs available at: http://localhost:8000/docs

### 6. Run the Dashboard

```bash
python -m streamlit run dashboard/app.py
```

Dashboard available at: http://localhost:8501

### Alternative: Docker Compose

```bash
docker-compose up --build
```

This starts both the API (port 8000) and dashboard (port 8501).

## Deployment (Render)

### Manual Deployment

**API Service:**
1. New > Web Service > Connect repo
2. Runtime: Docker
3. Dockerfile Path: `./Dockerfile`
4. Add environment variables:

| Variable | Value |
|----------|-------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your anon public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Your service role key |
| `SUPABASE_JWT_SECRET` | Your JWT secret |
| `GEMINI_API_KEY` | Your Gemini API key |
| `FIRECRAWL_API_KEY` | Your Firecrawl key |
| `SERVICE_API_KEY` | Any random string |
| `MATCH_THRESHOLD` | 80 |
| `LOG_LEVEL` | INFO |

**Dashboard Service:**
1. New > Web Service > Connect repo
2. Runtime: Docker
3. Dockerfile Path: `./Dockerfile.dashboard`
4. Add environment variables:

| Variable | Value |
|----------|-------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your anon public key |
| `API_BASE_URL` | Your deployed API URL |

## GitHub Actions Setup

1. Go to your repo > Settings > Secrets and variables > Actions
2. Add these secrets:
   - `API_BASE_URL`: Your Render API URL
   - `SERVICE_API_KEY`: The same key from your `.env`
3. The workflow runs automatically every 6 hours
4. Trigger manually from the Actions tab

## Project Structure

```
app/
  main.py              # FastAPI entry point
  config.py            # Environment configuration
  database.py          # Supabase client
  auth.py              # JWT authentication
  models/
    schemas.py         # Pydantic models
    enums.py           # Status enums
  routers/
    resumes.py         # Resume CRUD endpoints
    sources.py         # Company source endpoints
    jobs.py            # Job match endpoints
    scraping.py        # Scrape trigger endpoint
  services/
    resume_parser.py   # PDF parsing + Gemini structuring
    scraper.py         # Firecrawl career page scraping
    matcher.py         # Gemini match scoring
    discord_alerts.py  # Discord webhook alerts
    scheduler.py       # Pipeline orchestrator

dashboard/
  app.py               # Streamlit entry point
  pages/
    1_Resume.py        # Resume upload page
    2_Sources.py       # Source management page
    3_Matches.py       # Match results page
    4_Settings.py      # Settings page
  components/
    auth_ui.py         # Login/register UI
    charts.py          # Plotly chart components

tests/                 # Pytest test suite
sql/schema.sql         # Database schema
render.yaml            # Render deployment config
docker-compose.yml     # Local dev setup
.github/workflows/     # GitHub Actions cron
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/resumes/upload` | Upload + parse resume PDF |
| `GET` | `/api/resumes/current` | Get current resume |
| `DELETE` | `/api/resumes/{id}` | Delete resume |
| `POST` | `/api/sources` | Add career page URL |
| `GET` | `/api/sources` | List all sources |
| `PATCH` | `/api/sources/{id}` | Update source |
| `DELETE` | `/api/sources/{id}` | Remove source |
| `GET` | `/api/jobs` | List matches (with filters) |
| `GET` | `/api/jobs/{id}` | Match detail |
| `PATCH` | `/api/jobs/{id}/status` | Update match status |
| `GET` | `/api/jobs/export/csv` | Export matches CSV |
| `POST` | `/api/scraping/trigger` | Trigger scrape run |
| `GET` | `/api/scraping/history` | Scrape run logs |

All endpoints except `/health` and `/` require `Authorization: Bearer <token>`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase anon/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Service role key |
| `SUPABASE_JWT_SECRET` | Yes | JWT verification secret |
| `GEMINI_API_KEY` | Yes | Google Gemini API key (free at aistudio.google.com) |
| `FIRECRAWL_API_KEY` | No | Firecrawl API key for scraping |
| `DISCORD_WEBHOOK_URL` | No | Default Discord webhook for alerts |
| `SERVICE_API_KEY` | No | Key for GitHub Actions triggers |
| `MATCH_THRESHOLD` | No | Alert threshold (default: 80) |
| `SCRAPE_MAX_JOBS_PER_SOURCE` | No | Max jobs per scrape (default: 50) |

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Run a specific test file
pytest tests/test_matcher.py -v
```

## License

MIT

## Author

**Aman Sharma**
- GitHub: [aman00077777](https://github.com/aman00077777)
- Project: [AI Resume-Job Matcher](https://github.com/aman00077777/AI_Resume-Job_Matcher)