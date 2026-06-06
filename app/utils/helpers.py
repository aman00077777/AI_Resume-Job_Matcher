"""Shared utility functions."""

import csv
import io
from datetime import datetime


def generate_csv_export(matches: list[dict]) -> str:
    """Generate a CSV string from a list of job match records.

    Args:
        matches: List of match dicts with job and score data.

    Returns:
        CSV-formatted string ready for download.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Job Title",
        "Company",
        "Location",
        "Overall Score",
        "Skills Score",
        "Experience Score",
        "Title Score",
        "Location Score",
        "Matching Skills",
        "Missing Skills",
        "Summary",
        "Status",
        "Job URL",
        "Match Date",
    ])

    for m in matches:
        writer.writerow([
            m.get("job_title", ""),
            m.get("company_name", ""),
            m.get("job_location", ""),
            m.get("overall_score", 0),
            m.get("skills_score", 0),
            m.get("experience_score", 0),
            m.get("title_score", 0),
            m.get("location_score", 0),
            "; ".join(m.get("matching_skills", [])),
            "; ".join(m.get("missing_skills", [])),
            m.get("summary", ""),
            m.get("status", "new"),
            m.get("job_url", ""),
            m.get("created_at", ""),
        ])

    return output.getvalue()


def format_datetime(dt: datetime | str | None) -> str:
    """Format a datetime for display. Handles ISO strings and datetime objects."""
    if dt is None:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt
    return dt.strftime("%Y-%m-%d %H:%M UTC")
