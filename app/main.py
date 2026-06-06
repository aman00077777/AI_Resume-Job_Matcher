"""FastAPI application entry point.

Mounts all routers, configures CORS and logging, and provides
a health check endpoint for Render's health monitoring.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import get_settings
from app.routers import resumes, sources, jobs, scraping


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    settings = get_settings()
    logger.info("AI Resume-Job Matcher API starting up")
    logger.info(f"Match threshold: {settings.match_threshold}%")
    logger.info(f"Max jobs per source: {settings.scrape_max_jobs_per_source}")
    yield
    logger.info("API shutting down")


app = FastAPI(
    title="AI Resume-Job Matcher API",
    description=(
        "An AI-powered system that scrapes company career pages, evaluates "
        "job-candidate fit using Claude, and sends Discord alerts for strong matches."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",   # Local Streamlit
        "http://localhost:3000",   # Local frontend
        "https://*.onrender.com",  # Render deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────

app.include_router(resumes.router)
app.include_router(sources.router)
app.include_router(jobs.router)
app.include_router(scraping.router)


# ─── Health Check ────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint for Render monitoring and uptime checks."""
    return {"status": "healthy", "service": "ai-resume-matcher-api"}


@app.get("/", tags=["system"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "AI Resume-Job Matcher API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
