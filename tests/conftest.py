"""Shared test fixtures for mocking external services.

All external API calls (Supabase, Claude, Firecrawl, Discord) are mocked
so tests run without credentials and without making network requests.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set environment variables immediately at module load time before any app imports
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_KEY"] = "test-anon-key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-key"
os.environ["SUPABASE_JWT_SECRET"] = "test-jwt-secret"
os.environ["GEMINI_API_KEY"] = "AIzaSy-test-key"
os.environ["FIRECRAWL_API_KEY"] = "fc-test-key"
os.environ["DISCORD_WEBHOOK_URL"] = "https://discord.com/api/webhooks/test/test"
os.environ["SERVICE_API_KEY"] = "test-service-api-key"

import app.database

# Global variables to hold active mock clients for the currently running test
_active_supabase_client = None
_active_service_client = None

def mock_get_supabase_client():
    return _active_supabase_client

def mock_get_service_client():
    return _active_service_client

# Overwrite database client getters to dynamically return the active mock client
app.database.get_supabase_client = mock_get_supabase_client
app.database.get_service_client = mock_get_service_client


# ─── Environment setup ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Set required environment variables for testing (kept for compatibility)."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-test-key")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-key")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/test")
    monkeypatch.setenv("SERVICE_API_KEY", "test-service-api-key")


# ─── Sample Data ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_resume_text():
    """Sample resume text for testing."""
    return """
    John Doe
    Senior Software Engineer

    Experience:
    - Senior Software Engineer at TechCorp (2021-Present)
      - Led development of microservices architecture using Python and FastAPI
      - Implemented CI/CD pipelines with GitHub Actions
      - Managed team of 5 engineers

    - Software Engineer at StartupXYZ (2018-2021)
      - Built full-stack applications with React and Node.js
      - Designed REST APIs and GraphQL endpoints
      - PostgreSQL database design and optimization

    Skills: Python, JavaScript, TypeScript, React, FastAPI, PostgreSQL,
    Docker, Kubernetes, AWS, Git, CI/CD, Machine Learning, SQL

    Education:
    - B.S. Computer Science, MIT, 2018

    Location: San Francisco, CA (Open to Remote)
    """


@pytest.fixture
def sample_resume_data():
    """Pre-parsed resume data dict."""
    return {
        "skills": [
            "Python", "JavaScript", "TypeScript", "React", "FastAPI",
            "PostgreSQL", "Docker", "Kubernetes", "AWS", "Git",
            "CI/CD", "Machine Learning", "SQL",
        ],
        "experience_years": 6,
        "education": [
            {"degree": "B.S. Computer Science", "institution": "MIT", "year": "2018"}
        ],
        "job_titles": ["Senior Software Engineer", "Software Engineer"],
        "summary": "Experienced software engineer with 6 years in full-stack development and cloud infrastructure.",
    }


@pytest.fixture
def sample_job_description():
    """Sample job posting content."""
    return """
    # Senior Backend Engineer

    We're looking for a Senior Backend Engineer to join our platform team.

    ## Requirements:
    - 5+ years of experience in backend development
    - Strong proficiency in Python
    - Experience with FastAPI or Django
    - PostgreSQL and database design
    - Docker and Kubernetes
    - AWS or GCP experience
    - CI/CD pipeline experience

    ## Nice to have:
    - Machine Learning experience
    - GraphQL
    - TypeScript

    ## Location: Remote (US)

    ## Salary: $150k - $200k
    """


@pytest.fixture
def sample_pdf_bytes():
    """Generate minimal valid PDF bytes for testing.

    This creates the simplest possible valid PDF that contains text.
    """
    # Minimal PDF with text content
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj

2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj

3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj

4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (John Doe) Tj ET
endstream
endobj

5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj

xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000360 00000 n 

trailer
<< /Root 1 0 R /Size 6 >>
startxref
441
%%EOF"""
    return pdf_content


@pytest.fixture
def mock_gemini_resume_response():
    """Mock Gemini response for resume parsing."""
    inner_json = json.dumps({
        "skills": ["Python", "JavaScript", "React", "FastAPI", "PostgreSQL"],
        "experience_years": 6,
        "education": [{"degree": "B.S. Computer Science", "institution": "MIT", "year": "2018"}],
        "job_titles": ["Senior Software Engineer", "Software Engineer"],
        "summary": "Experienced engineer with 6 years in full-stack development.",
    })
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": inner_json}
                    ]
                }
            }
        ]
    }


@pytest.fixture
def mock_gemini_match_response():
    """Mock Gemini response for job matching."""
    inner_json = json.dumps({
        "skills_score": 85,
        "experience_score": 90,
        "title_score": 80,
        "location_score": 100,
        "matching_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "missing_skills": ["GraphQL"],
        "summary": "Strong match. Candidate has most required skills and appropriate experience level.",
    })
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": inner_json}
                    ]
                }
            }
        ]
    }


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    mock = MagicMock()
    return mock


@pytest.fixture
def api_client(set_test_env):
    """Create a FastAPI test client with mocked dependencies."""
    global _active_supabase_client, _active_service_client

    mock_client = MagicMock()
    _active_supabase_client = mock_client
    _active_service_client = mock_client

    # Mock auth to return a test user
    mock_user = MagicMock()
    mock_user.user.id = "test-user-id"
    mock_user.user.email = "test@example.com"
    mock_client.auth.get_user.return_value = mock_user

    from app.main import app
    client = TestClient(app)

    yield client, mock_client

    # Reset active mocks after test
    _active_supabase_client = None
    _active_service_client = None
