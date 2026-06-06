"""Scraping trigger and history endpoints."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from loguru import logger

from app.auth import get_current_user
from app.database import get_supabase_client
from app.models.schemas import ScrapeRunResponse
from app.services.scheduler import run_scrape_and_match_for_user, run_scrape_and_match_all_users

router = APIRouter(prefix="/api/scraping", tags=["scraping"])


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Trigger a scrape-and-match run.

    For user auth: runs for that specific user.
    For service auth: runs for ALL users with active sources.

    The scraping runs in the background so this endpoint returns immediately.
    """
    if current_user.get("is_service"):
        logger.info("Service-triggered scrape: processing all users")
        background_tasks.add_task(run_scrape_and_match_all_users)
        return {
            "message": "Scrape-and-match triggered for all users.",
            "mode": "all_users",
        }
    else:
        user_id = current_user["id"]
        logger.info(f"User-triggered scrape for {user_id}")
        background_tasks.add_task(run_scrape_and_match_for_user, user_id)
        return {
            "message": "Scrape-and-match triggered for your account.",
            "mode": "single_user",
            "user_id": user_id,
        }


@router.get("/history", response_model=list[ScrapeRunResponse])
async def get_scrape_history(
    current_user: dict = Depends(get_current_user),
    limit: int = 20,
):
    """Get past scrape run logs for the current user."""
    if current_user.get("is_service"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service key cannot view user-specific history.",
        )

    db = get_supabase_client()

    result = (
        db.table("scrape_runs")
        .select("*")
        .eq("user_id", current_user["id"])
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )

    return [
        ScrapeRunResponse(
            id=row["id"],
            user_id=row["user_id"],
            started_at=row["started_at"],
            completed_at=row.get("completed_at"),
            jobs_found=row.get("jobs_found", 0),
            new_jobs=row.get("new_jobs", 0),
            matches_found=row.get("matches_found", 0),
            alerts_sent=row.get("alerts_sent", 0),
            errors=row.get("errors", []),
        )
        for row in result.data
    ]
