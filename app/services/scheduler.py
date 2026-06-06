"""Orchestrator: ties scraping, matching, and alerting together.

This is the main pipeline that runs on a schedule (GitHub Actions)
or is triggered manually. For each user, it:
1. Scrapes all active company sources for new job listings.
2. Evaluates each new listing against the user's resume with Claude.
3. Sends Discord alerts for matches above the user's threshold.
4. Logs the entire run for audit.
"""

from datetime import datetime, timezone

from loguru import logger

from app.config import get_settings
from app.database import get_service_client
from app.services.scraper import scrape_career_page, ScrapingError
from app.services.matcher import evaluate_match
from app.services.discord_alerts import send_match_alert, send_scrape_summary


def run_scrape_and_match_for_user(user_id: str) -> dict:
    """Execute the full scrape -> match -> alert pipeline for a single user.

    Args:
        user_id: UUID of the user to process.

    Returns:
        Summary dict with counts: jobs_found, new_jobs, matches_found,
        alerts_sent, errors.
    """
    db = get_service_client()  # Service role to bypass RLS
    settings = get_settings()

    stats = {
        "jobs_found": 0,
        "new_jobs": 0,
        "matches_found": 0,
        "alerts_sent": 0,
        "errors": [],
    }

    # ── Create scrape run log ────────────────────────────────────────────
    run_response = db.table("scrape_runs").insert({
        "user_id": user_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    run_id = run_response.data[0]["id"] if run_response.data else None

    # ── Load user profile ────────────────────────────────────────────────
    user_response = db.table("users").select("*").eq("id", user_id).execute()
    if not user_response.data:
        logger.error(f"User {user_id} not found")
        stats["errors"].append(f"User {user_id} not found")
        return stats

    user = user_response.data[0]
    webhook_url = user.get("discord_webhook_url") or settings.discord_webhook_url
    threshold = user.get("match_threshold", settings.match_threshold)
    location_preference = user.get("location_preference", "")

    # ── Load user's resume ───────────────────────────────────────────────
    resume_response = (
        db.table("resumes")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not resume_response.data:
        logger.warning(f"User {user_id} has no resume uploaded, skipping")
        stats["errors"].append("No resume uploaded")
        _finalize_run(db, run_id, stats)
        return stats

    resume = resume_response.data[0]
    resume_data = {
        "skills": resume.get("skills", []),
        "experience_years": resume.get("experience_years", 0),
        "education": resume.get("education", []),
        "job_titles": resume.get("job_titles", []),
        "summary": resume.get("summary", ""),
    }

    # ── Load active company sources ──────────────────────────────────────
    sources_response = (
        db.table("company_sources")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .execute()
    )

    if not sources_response.data:
        logger.info(f"User {user_id} has no active sources")
        _finalize_run(db, run_id, stats)
        return stats

    # ── Process each source ──────────────────────────────────────────────
    for source in sources_response.data:
        source_id = source["id"]
        company_name = source["company_name"]
        career_url = source["career_url"]

        logger.info(f"Processing source: {company_name} ({career_url})")

        try:
            # Get existing content hashes for this source
            existing_response = (
                db.table("job_listings")
                .select("content_hash")
                .eq("source_id", source_id)
                .execute()
            )
            existing_hashes = {
                row["content_hash"]
                for row in existing_response.data
                if row.get("content_hash")
            }

            # Scrape the career page
            scraped_jobs = scrape_career_page(career_url, existing_hashes)
            stats["jobs_found"] += len(scraped_jobs)

            # Insert new jobs and evaluate matches
            for job in scraped_jobs:
                # Insert job listing
                job_insert = db.table("job_listings").insert({
                    "source_id": source_id,
                    "title": job.title,
                    "description": job.description,
                    "location": job.location,
                    "url": job.url,
                    "content_hash": job.content_hash,
                }).execute()

                if not job_insert.data:
                    continue

                job_id = job_insert.data[0]["id"]
                stats["new_jobs"] += 1

                # Evaluate match with Claude
                match_result = evaluate_match(
                    resume_data=resume_data,
                    job_title=job.title,
                    job_description=job.description,
                    job_location=job.location,
                    location_preference=location_preference,
                )

                # Insert match result
                db.table("job_matches").insert({
                    "job_id": job_id,
                    "resume_id": resume["id"],
                    "overall_score": match_result["overall_score"],
                    "skills_score": match_result["skills_score"],
                    "experience_score": match_result["experience_score"],
                    "title_score": match_result["title_score"],
                    "location_score": match_result["location_score"],
                    "matching_skills": match_result["matching_skills"],
                    "missing_skills": match_result["missing_skills"],
                    "summary": match_result["summary"],
                }).execute()

                # Send Discord alert if above threshold
                if match_result["overall_score"] >= threshold:
                    stats["matches_found"] += 1

                    alert_sent = send_match_alert(
                        job_title=job.title,
                        company_name=company_name,
                        overall_score=match_result["overall_score"],
                        skills_score=match_result["skills_score"],
                        experience_score=match_result["experience_score"],
                        title_score=match_result["title_score"],
                        location_score=match_result["location_score"],
                        matching_skills=match_result["matching_skills"],
                        missing_skills=match_result["missing_skills"],
                        summary=match_result["summary"],
                        job_url=job.url,
                        job_location=job.location,
                        webhook_url=webhook_url,
                    )

                    if alert_sent:
                        stats["alerts_sent"] += 1

            # Update last_scraped_at on the source
            db.table("company_sources").update({
                "last_scraped_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", source_id).execute()

        except ScrapingError as e:
            error_msg = f"Scraping failed for {company_name}: {e}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error processing {company_name}: {e}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)

    # ── Send summary notification ────────────────────────────────────────
    send_scrape_summary(
        webhook_url=webhook_url,
        jobs_found=stats["jobs_found"],
        new_jobs=stats["new_jobs"],
        matches_above_threshold=stats["matches_found"],
        alerts_sent=stats["alerts_sent"],
        errors=stats["errors"],
    )

    # ── Finalize run log ─────────────────────────────────────────────────
    _finalize_run(db, run_id, stats)

    logger.info(
        f"Scrape run complete for user {user_id}: "
        f"{stats['new_jobs']} new jobs, {stats['matches_found']} matches, "
        f"{stats['alerts_sent']} alerts"
    )

    return stats


def run_scrape_and_match_all_users() -> list[dict]:
    """Run the pipeline for all users who have active sources.

    Called by GitHub Actions cron. Returns a list of per-user summaries.
    """
    db = get_service_client()

    # Get all users who have at least one active source
    users_response = (
        db.table("company_sources")
        .select("user_id")
        .eq("is_active", True)
        .execute()
    )

    user_ids = list({row["user_id"] for row in users_response.data})
    logger.info(f"Running scrape-and-match for {len(user_ids)} users")

    results = []
    for user_id in user_ids:
        try:
            summary = run_scrape_and_match_for_user(user_id)
            summary["user_id"] = user_id
            results.append(summary)
        except Exception as e:
            logger.error(f"Pipeline failed for user {user_id}: {e}")
            results.append({"user_id": user_id, "error": str(e)})

    return results


def _finalize_run(db, run_id: str | None, stats: dict):
    """Update the scrape_runs record with final stats."""
    if not run_id:
        return

    try:
        db.table("scrape_runs").update({
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "jobs_found": stats.get("jobs_found", 0),
            "new_jobs": stats.get("new_jobs", 0),
            "matches_found": stats.get("matches_found", 0),
            "alerts_sent": stats.get("alerts_sent", 0),
            "errors": stats.get("errors", []),
        }).eq("id", run_id).execute()
    except Exception as e:
        logger.error(f"Failed to finalize scrape run {run_id}: {e}")
