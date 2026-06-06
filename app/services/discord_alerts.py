"""Discord webhook alert service.

Sends rich embed notifications for strong job matches. Each alert
includes the job title, company, match score breakdown, matching
skills, and a direct link to apply.
"""

import requests
from loguru import logger


def send_match_alert(
    job_title: str,
    company_name: str,
    overall_score: int,
    skills_score: int,
    experience_score: int,
    title_score: int,
    location_score: int,
    matching_skills: list[str],
    missing_skills: list[str],
    summary: str,
    job_url: str,
    job_location: str,
    webhook_url: str,
) -> bool:
    """Send a Discord embed notification for a strong job match.

    Args:
        job_title: Title of the matched job.
        company_name: Company offering the role.
        overall_score: Weighted overall match score (0-100).
        skills_score: Skills overlap score.
        experience_score: Experience level match score.
        title_score: Job title relevance score.
        location_score: Location compatibility score.
        matching_skills: Skills the candidate has that the job wants.
        missing_skills: Skills the job wants that the candidate lacks.
        summary: AI-generated explanation of the match.
        job_url: Direct link to the job posting / application.
        job_location: Location of the job.
        webhook_url: Discord webhook URL to send to.

    Returns:
        True if the alert was sent successfully, False otherwise.
    """
    if not webhook_url:
        logger.warning("No Discord webhook URL configured, skipping alert")
        return False

    # Color coding: green for 90+, amber for 80-89, blue for below
    if overall_score >= 90:
        color = 0x00E676  # Green
        grade = "Excellent Match"
    elif overall_score >= 80:
        color = 0xFFAB00  # Amber
        grade = "Strong Match"
    else:
        color = 0x2979FF  # Blue
        grade = "Good Match"

    # Score bar visualization
    score_bar = _build_score_bar(overall_score)

    # Format matching skills (cap at 10 for readability)
    skills_display = ", ".join(matching_skills[:10]) if matching_skills else "None identified"
    missing_display = ", ".join(missing_skills[:5]) if missing_skills else "None"

    embed = {
        "title": f"{job_title} at {company_name}",
        "url": job_url,
        "description": (
            f"**{grade}** {score_bar} **{overall_score}%**\n\n"
            f"{summary}"
        ),
        "color": color,
        "fields": [
            {
                "name": "Score Breakdown",
                "value": (
                    f"Skills: **{skills_score}%** | "
                    f"Experience: **{experience_score}%** | "
                    f"Title Fit: **{title_score}%** | "
                    f"Location: **{location_score}%**"
                ),
                "inline": False,
            },
            {
                "name": "Your Matching Skills",
                "value": skills_display,
                "inline": False,
            },
            {
                "name": "Skills to Brush Up On",
                "value": missing_display,
                "inline": True,
            },
            {
                "name": "Location",
                "value": job_location or "Not specified",
                "inline": True,
            },
        ],
        "footer": {
            "text": "AI Resume-Job Matcher | Click the title to apply",
        },
    }

    payload = {
        "username": "Job Match Bot",
        "embeds": [embed],
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 204:
            logger.info(f"Discord alert sent: {job_title} at {company_name} ({overall_score}%)")
            return True
        else:
            logger.error(
                f"Discord webhook returned {response.status_code}: {response.text}"
            )
            return False

    except requests.RequestException as e:
        logger.error(f"Failed to send Discord alert: {e}")
        return False


def send_scrape_summary(
    webhook_url: str,
    jobs_found: int,
    new_jobs: int,
    matches_above_threshold: int,
    alerts_sent: int,
    errors: list[str],
) -> bool:
    """Send a summary notification after a scrape run completes.

    Args:
        webhook_url: Discord webhook URL.
        jobs_found: Total jobs discovered.
        new_jobs: New jobs not previously seen.
        matches_above_threshold: Jobs scoring above the user's threshold.
        alerts_sent: Individual match alerts sent.
        errors: List of error messages from the run.

    Returns:
        True if sent successfully.
    """
    if not webhook_url:
        return False

    color = 0x00E676 if not errors else 0xFFAB00

    description = (
        f"**Jobs Found:** {jobs_found}\n"
        f"**New Jobs:** {new_jobs}\n"
        f"**Strong Matches:** {matches_above_threshold}\n"
        f"**Alerts Sent:** {alerts_sent}"
    )

    if errors:
        error_text = "\n".join(f"- {e}" for e in errors[:5])
        description += f"\n\n**Errors:**\n{error_text}"

    embed = {
        "title": "Scrape Run Complete",
        "description": description,
        "color": color,
        "footer": {"text": "AI Resume-Job Matcher"},
    }

    try:
        response = requests.post(
            webhook_url,
            json={"username": "Job Match Bot", "embeds": [embed]},
            timeout=10,
        )
        return response.status_code == 204
    except requests.RequestException as e:
        logger.error(f"Failed to send scrape summary: {e}")
        return False


def _build_score_bar(score: int, length: int = 10) -> str:
    """Build a visual progress bar for the score."""
    filled = round(score / 100 * length)
    empty = length - filled
    return "[" + "=" * filled + "-" * empty + "]"
