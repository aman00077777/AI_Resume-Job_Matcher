"""Pydantic models for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl

from app.models.enums import MatchStatus


# ─── Resume ───────────────────────────────────────────────────────────────────

class EducationEntry(BaseModel):
    degree: str = ""
    institution: str = ""
    year: Optional[str] = None


class ParsedResume(BaseModel):
    """Structured data extracted from a resume PDF."""

    skills: list[str] = Field(default_factory=list)
    experience_years: int = 0
    education: list[EducationEntry] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    summary: str = ""


class ResumeResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    skills: list[str] = Field(default_factory=list)
    experience_years: int = 0
    education: list[EducationEntry] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    summary: str = ""
    parsed_at: datetime


# ─── Company Sources ──────────────────────────────────────────────────────────

class CompanySourceCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    career_url: str = Field(..., min_length=5)


class CompanySourceUpdate(BaseModel):
    company_name: Optional[str] = None
    career_url: Optional[str] = None
    is_active: Optional[bool] = None


class CompanySourceResponse(BaseModel):
    id: str
    user_id: str
    company_name: str
    career_url: str
    is_active: bool
    last_scraped_at: Optional[datetime] = None
    created_at: datetime


# ─── Job Listings ─────────────────────────────────────────────────────────────

class JobListingResponse(BaseModel):
    id: str
    source_id: str
    title: str
    description: str = ""
    location: str = ""
    url: str
    scraped_at: datetime


# ─── Job Matches ──────────────────────────────────────────────────────────────

class MatchScoreBreakdown(BaseModel):
    """Score breakdown returned by the Claude matching engine."""

    skills_score: int = Field(0, ge=0, le=100)
    experience_score: int = Field(0, ge=0, le=100)
    title_score: int = Field(0, ge=0, le=100)
    location_score: int = Field(0, ge=0, le=100)
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    summary: str = ""


class JobMatchResponse(BaseModel):
    id: str
    job_id: str
    resume_id: str
    overall_score: int
    skills_score: int
    experience_score: int
    title_score: int
    location_score: int
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    summary: str = ""
    status: MatchStatus = MatchStatus.NEW
    created_at: datetime
    # Joined fields (populated in list queries)
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    job_url: Optional[str] = None
    job_location: Optional[str] = None


class MatchStatusUpdate(BaseModel):
    status: MatchStatus


class MatchFilter(BaseModel):
    """Query parameters for filtering job matches."""

    min_score: int = Field(0, ge=0, le=100)
    max_score: int = Field(100, ge=0, le=100)
    status: Optional[MatchStatus] = None
    company: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


# ─── Scrape Runs ──────────────────────────────────────────────────────────────

class ScrapeRunResponse(BaseModel):
    id: str
    user_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    jobs_found: int = 0
    new_jobs: int = 0
    matches_found: int = 0
    alerts_sent: int = 0
    errors: list = Field(default_factory=list)


# ─── User Profile ─────────────────────────────────────────────────────────────

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    location_preference: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    match_threshold: Optional[int] = Field(None, ge=0, le=100)


class UserProfileResponse(BaseModel):
    id: str
    full_name: str = ""
    location_preference: str = ""
    discord_webhook_url: str = ""
    match_threshold: int = 80
