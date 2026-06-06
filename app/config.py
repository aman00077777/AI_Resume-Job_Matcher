"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration for the application.

    Values are loaded from a .env file or environment variables.
    See .env.example for the full list of variables.
    """

    # --- Supabase ---
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_key: str = Field(..., description="Supabase anon/public key")
    supabase_service_role_key: str = Field(..., description="Supabase service role key")
    supabase_jwt_secret: str = Field(..., description="Supabase JWT secret for token verification")

    # --- Gemini ---
    gemini_api_key: str = Field(..., description="Gemini API key")

    # --- Firecrawl ---
    firecrawl_api_key: str = Field(..., description="Firecrawl API key")

    # --- Discord ---
    discord_webhook_url: str = Field(default="", description="Default Discord webhook URL")

    # --- Application Settings ---
    match_threshold: int = Field(default=80, ge=0, le=100, description="Minimum match score for alerts")
    scrape_max_jobs_per_source: int = Field(default=50, ge=1, description="Max jobs to scrape per career page")
    log_level: str = Field(default="INFO", description="Logging level")

    # --- API Settings ---
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")

    # --- Service API Key (for GitHub Actions automated triggers) ---
    service_api_key: str = Field(default="", description="API key for service-to-service calls")

    # --- External ---
    api_base_url: str = Field(default="http://localhost:8000", description="Base URL of deployed API")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
