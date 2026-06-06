# AI Resume-Job Matching Application

An end-to-end AI-powered system that monitors company career pages, evaluates job-candidate fit using Claude AI, and sends Discord alerts when strong matches are found.

## How It Works

```
Resume (PDF)                    Career Page URLs
     |                                |
     v                                v
 PyPDF2 text extraction       Firecrawl scraping
     |                                |
     v                                v
 Claude structures resume      Job listings extracted
     |                                |
     +----------+   +-----------+-----+
                |   |
                v   v
        Claude Match Scoring
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

- **Resume Parsing** -- Upload PDF, AI extracts skills, experience, education
- **Smart Scraping** -- Firecrawl handles JavaScript-heavy career pages
- **AI Matching** -- Claude evaluates fit across 4 weighted criteria
- **Discord Alerts** -- Instant notifications for strong matches (80%+)
- **Streamlit Dashboard** -- Manage sources, view matches, export to CSV
- **Scheduled Runs** -- GitHub Actions triggers scraping every 6 hours
- **Multi-user** -- Supabase Auth with per-user data isolation (RLS)

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
| AI Matching | Claude 3.5 Sonnet (Anthropic) |
| Database | Supabase (PostgreSQL) |
| Dashboard | Streamlit |
| Auth | Supabase Auth (JWT) |
| Alerts | Discord Webhooks |
| Scheduling | GitHub Actions (cron) |
| Deployment | Render (API + Dashboard) |

## Prerequisites

- Python 3.10+
- [Supabase account](https://supabase.com) (free tier)
- [Anthropic API key](https://console.anthropic.com)
- [Firecrawl API key](https://www.firecrawl.dev)
- [Discord webhook URL](https://support.discord.com/hc/en-us/articles/228383668)

## Quick Start (Local Development)

### 1. Clone and install

```bash
git clone <your-repo-url>
cd "AI Resume-Job Matching application"
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Set up Supabase database

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** in your dashboard
3. Copy and paste the contents of `sql/schema.sql`
4. Click **Run** to create all tables and policies
5. Copy your project URL and keys from **Settings > API**

### 4. Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 5. Run the Dashboard

```bash
# Create Streamlit secrets file
mkdir .streamlit
echo '[secrets]' > .streamlit/secrets.toml
echo 'SUPABASE_URL = "your-url"' >> .streamlit/secrets.toml
echo 'SUPABASE_KEY = "your-key"' >> .streamlit/secrets.toml

# Launch
streamlit run dashboard/app.py
```

Dashboard available at: http://localhost:8501

### Alternative: Docker Compose

```bash
docker-compose up --build
```

This starts both the API (port 8000) and dashboard (port 8501).

## Deployment (Render)

### Option A: Render Blueprint (Recommended)

1. Push your code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **New > Blueprint**
4. Connect your GitHub repo
5. Render will detect `render.yaml` and create both services
6. Add environment variables in each service's settings

### Option B: Manual Deployment

**API Service:**
1. New > Web Service > Connect repo
2. Runtime: Docker
3. Dockerfile Path: `./Dockerfile`
4. Add all env vars from `.env.example`

**Dashboard Service:**
1. New > Web Service > Connect repo
2. Runtime: Docker
3. Dockerfile Path: `./Dockerfile.dashboard`
4. Add `SUPABASE_URL`, `SUPABASE_KEY`, and `API_BASE_URL` env vars
5. Set `API_BASE_URL` to your API service's URL

## GitHub Actions Setup

1. Go to your repo > Settings > Secrets and variables > Actions
2. Add these secrets:
   - `API_BASE_URL`: Your Render API URL (e.g., `https://ai-job-matcher-api.onrender.com`)
   - `SERVICE_API_KEY`: The same key from your `.env`
3. The workflow runs automatically every 6 hours
4. You can also trigger it manually from the Actions tab

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
    resume_parser.py   # PDF parsing + Claude structuring
    scraper.py         # Firecrawl career page scraping
    matcher.py         # Claude match scoring
    discord_alerts.py  # Discord webhook alerts
    scheduler.py       # Pipeline orchestrator
  utils/
    helpers.py         # CSV export, utilities

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
sql/schema.sql         # Database migration
render.yaml            # Render deployment blueprint
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

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Run a specific test file
pytest tests/test_matcher.py -v
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase anon/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Service role key (for background jobs) |
| `SUPABASE_JWT_SECRET` | Yes | JWT verification secret |
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `FIRECRAWL_API_KEY` | Yes | Firecrawl API key |
| `DISCORD_WEBHOOK_URL` | No | Default Discord webhook |
| `SERVICE_API_KEY` | No | Key for GitHub Actions triggers |
| `MATCH_THRESHOLD` | No | Alert threshold (default: 80) |
| `SCRAPE_MAX_JOBS_PER_SOURCE` | No | Max jobs per scrape (default: 50) |

## License

MIT
#   A I _ R e s u m e - J o b _ M a t c h e r  
 