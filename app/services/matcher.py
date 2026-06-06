"""Claude-powered job-candidate matching engine.

Uses Claude 3.5 Sonnet to evaluate how well a candidate's resume
matches a job posting. Produces a weighted score (0-100) with
breakdown across four criteria.
"""

import json

from anthropic import Anthropic
from loguru import logger

from app.config import get_settings
from app.models.schemas import MatchScoreBreakdown

# ─── Scoring Weights ─────────────────────────────────────────────────────────

WEIGHTS = {
    "skills": 0.35,
    "experience": 0.25,
    "title": 0.25,
    "location": 0.15,
}

# ─── Claude Matching Prompt ──────────────────────────────────────────────────

MATCH_PROMPT = """You are an expert technical recruiter AI. Your task is to evaluate how well a candidate matches a specific job posting.

## Candidate Profile

**Skills:** {skills}
**Experience:** {experience_years} years
**Previous Titles:** {job_titles}
**Education:** {education}
**Location Preference:** {location_preference}
**Summary:** {candidate_summary}

## Job Posting

**Title:** {job_title}
**Location:** {job_location}
**Description:**
{job_description}

## Scoring Instructions

Evaluate the match on each of these four criteria. Rate each from 0 to 100:

1. **skills_score**: What percentage of the required and preferred skills does the candidate possess? Consider equivalent technologies (e.g., React ~ Vue, AWS ~ GCP). 100 = has all required + most preferred skills. 0 = no relevant skills.

2. **experience_score**: How well does the candidate's experience level match what the job requires? Consider both years and depth. 100 = perfect experience match. 50 = slightly over/under-qualified. 0 = vastly mismatched (e.g., entry-level applying for VP).

3. **title_score**: How relevant is this role to the candidate's career trajectory? Would this be a logical next step or lateral move? 100 = direct match or clear promotion path. 0 = completely unrelated field.

4. **location_score**: Does the job's location work for the candidate? 100 = remote role or matching city. 50 = hybrid in a nearby area. 0 = relocation required with no indication of willingness. If the job says "Remote" or the location is unclear, default to 80.

Also identify:
- **matching_skills**: Skills the candidate has that the job requires.
- **missing_skills**: Skills the job requires that the candidate lacks.
- **summary**: 2-3 sentences explaining why this is or isn't a good fit. Be specific and actionable.

Return ONLY a valid JSON object with these exact keys:
{{
  "skills_score": <int>,
  "experience_score": <int>,
  "title_score": <int>,
  "location_score": <int>,
  "matching_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3"],
  "summary": "<your explanation>"
}}

No markdown, no code fences, no extra text."""


def _format_education(education: list[dict]) -> str:
    """Format education entries for the prompt."""
    if not education:
        return "Not specified"
    parts = []
    for edu in education:
        entry = edu.get("degree", "Degree")
        if edu.get("institution"):
            entry += f" from {edu['institution']}"
        if edu.get("year"):
            entry += f" ({edu['year']})"
        parts.append(entry)
    return "; ".join(parts)


def calculate_overall_score(breakdown: MatchScoreBreakdown) -> int:
    """Calculate the weighted overall match score.

    Weights:
        - Skills overlap:       35%
        - Experience level:     25%
        - Job title relevance:  25%
        - Location preference:  15%

    Returns:
        Integer score from 0 to 100.
    """
    score = (
        WEIGHTS["skills"] * breakdown.skills_score
        + WEIGHTS["experience"] * breakdown.experience_score
        + WEIGHTS["title"] * breakdown.title_score
        + WEIGHTS["location"] * breakdown.location_score
    )
    return round(score)


def evaluate_match(
    resume_data: dict,
    job_title: str,
    job_description: str,
    job_location: str = "",
    location_preference: str = "",
) -> dict:
    """Use Claude to evaluate how well a resume matches a job posting.

    Args:
        resume_data: Parsed resume dict with skills, experience_years,
            education, job_titles, summary.
        job_title: Title of the job posting.
        job_description: Full job description text.
        job_location: Location from the job posting.
        location_preference: User's preferred location / openness to relocation.

    Returns:
        Dictionary containing overall_score, individual scores,
        matching/missing skills, and summary. Ready for DB insert.
    """
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

    prompt = MATCH_PROMPT.format(
        skills=", ".join(resume_data.get("skills", [])),
        experience_years=resume_data.get("experience_years", 0),
        job_titles=", ".join(resume_data.get("job_titles", [])),
        education=_format_education(resume_data.get("education", [])),
        location_preference=location_preference or "Not specified",
        candidate_summary=resume_data.get("summary", "Not available"),
        job_title=job_title,
        job_location=job_location or "Not specified",
        job_description=job_description[:8000],  # Cap to manage tokens
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()

        # Strip code fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        data = json.loads(response_text)

        breakdown = MatchScoreBreakdown(
            skills_score=_clamp(data.get("skills_score", 0)),
            experience_score=_clamp(data.get("experience_score", 0)),
            title_score=_clamp(data.get("title_score", 0)),
            location_score=_clamp(data.get("location_score", 0)),
            matching_skills=data.get("matching_skills", []),
            missing_skills=data.get("missing_skills", []),
            summary=data.get("summary", ""),
        )

        overall = calculate_overall_score(breakdown)

        logger.info(
            f"Match evaluated: '{job_title}' -> {overall}% "
            f"(skills={breakdown.skills_score}, exp={breakdown.experience_score}, "
            f"title={breakdown.title_score}, loc={breakdown.location_score})"
        )

        return {
            "overall_score": overall,
            "skills_score": breakdown.skills_score,
            "experience_score": breakdown.experience_score,
            "title_score": breakdown.title_score,
            "location_score": breakdown.location_score,
            "matching_skills": breakdown.matching_skills,
            "missing_skills": breakdown.missing_skills,
            "summary": breakdown.summary,
        }

    except json.JSONDecodeError as e:
        logger.error(f"Claude returned invalid JSON for match evaluation: {e}")
        return _fallback_scores(job_title)
    except Exception as e:
        logger.error(f"Match evaluation failed for '{job_title}': {e}")
        return _fallback_scores(job_title)


def _clamp(value: int | float, min_val: int = 0, max_val: int = 100) -> int:
    """Clamp a value to [min_val, max_val] and convert to int."""
    try:
        return max(min_val, min(max_val, int(value)))
    except (TypeError, ValueError):
        return 0


def _fallback_scores(job_title: str) -> dict:
    """Return zero scores when evaluation fails. The job is still stored
    so it can be re-evaluated later."""
    logger.warning(f"Using fallback scores for '{job_title}'")
    return {
        "overall_score": 0,
        "skills_score": 0,
        "experience_score": 0,
        "title_score": 0,
        "location_score": 0,
        "matching_skills": [],
        "missing_skills": [],
        "summary": "Match evaluation failed. This job will be re-evaluated in the next run.",
    }
