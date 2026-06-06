"""Job listings and match result endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger

from app.auth import require_user
from app.database import get_supabase_client
from app.models.enums import MatchStatus
from app.models.schemas import JobMatchResponse, MatchStatusUpdate
from app.utils.helpers import generate_csv_export

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/", response_model=list[JobMatchResponse])
async def list_matches(
    min_score: int = Query(0, ge=0, le=100),
    max_score: int = Query(100, ge=0, le=100),
    status_filter: Optional[MatchStatus] = Query(None, alias="status"),
    company: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_user),
):
    """List all job matches for the current user with optional filters.

    Filters:
    - min_score / max_score: Score range (0-100)
    - status: Match status (new, applied, not_interested, saved)
    - company: Company name (partial match)
    - date_from / date_to: Date range (ISO format)
    """
    db = get_supabase_client()

    # Get user's resume IDs for filtering
    resumes = (
        db.table("resumes")
        .select("id")
        .eq("user_id", current_user["id"])
        .execute()
    )

    resume_ids = [r["id"] for r in resumes.data]
    if not resume_ids:
        return []

    # Build query
    query = (
        db.table("job_matches")
        .select(
            "*, "
            "job_listings!inner(title, url, location, source_id, "
            "company_sources!inner(company_name))"
        )
        .in_("resume_id", resume_ids)
        .gte("overall_score", min_score)
        .lte("overall_score", max_score)
        .order("overall_score", desc=True)
        .range(offset, offset + limit - 1)
    )

    if status_filter:
        query = query.eq("status", status_filter.value)

    if date_from:
        query = query.gte("created_at", date_from)

    if date_to:
        query = query.lte("created_at", date_to)

    result = query.execute()

    matches = []
    for row in result.data:
        job = row.get("job_listings", {})
        source = job.get("company_sources", {})

        # Apply company filter (post-query since it's on a joined table)
        if company and company.lower() not in source.get("company_name", "").lower():
            continue

        matches.append(JobMatchResponse(
            id=row["id"],
            job_id=row["job_id"],
            resume_id=row["resume_id"],
            overall_score=row["overall_score"],
            skills_score=row["skills_score"],
            experience_score=row["experience_score"],
            title_score=row["title_score"],
            location_score=row["location_score"],
            matching_skills=row.get("matching_skills", []),
            missing_skills=row.get("missing_skills", []),
            summary=row.get("summary", ""),
            status=row["status"],
            created_at=row["created_at"],
            job_title=job.get("title"),
            company_name=source.get("company_name"),
            job_url=job.get("url"),
            job_location=job.get("location"),
        ))

    return matches


@router.get("/export/csv")
async def export_matches_csv(
    min_score: int = Query(0, ge=0, le=100),
    status_filter: Optional[MatchStatus] = Query(None, alias="status"),
    current_user: dict = Depends(require_user),
):
    """Export job matches as a CSV file download."""
    db = get_supabase_client()

    resumes = (
        db.table("resumes")
        .select("id")
        .eq("user_id", current_user["id"])
        .execute()
    )

    resume_ids = [r["id"] for r in resumes.data]
    if not resume_ids:
        csv_content = "No matches found"
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=job_matches.csv"},
        )

    query = (
        db.table("job_matches")
        .select(
            "*, "
            "job_listings!inner(title, url, location, "
            "company_sources!inner(company_name))"
        )
        .in_("resume_id", resume_ids)
        .gte("overall_score", min_score)
        .order("overall_score", desc=True)
        .limit(500)
    )

    if status_filter:
        query = query.eq("status", status_filter.value)

    result = query.execute()

    export_data = []
    for row in result.data:
        job = row.get("job_listings", {})
        source = job.get("company_sources", {})
        export_data.append({
            "job_title": job.get("title", ""),
            "company_name": source.get("company_name", ""),
            "job_location": job.get("location", ""),
            "overall_score": row["overall_score"],
            "skills_score": row["skills_score"],
            "experience_score": row["experience_score"],
            "title_score": row["title_score"],
            "location_score": row["location_score"],
            "matching_skills": row.get("matching_skills", []),
            "missing_skills": row.get("missing_skills", []),
            "summary": row.get("summary", ""),
            "status": row["status"],
            "job_url": job.get("url", ""),
            "created_at": row["created_at"],
        })

    csv_content = generate_csv_export(export_data)

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=job_matches.csv"},
    )


@router.get("/{match_id}", response_model=JobMatchResponse)
async def get_match_detail(
    match_id: str,
    current_user: dict = Depends(require_user),
):
    """Get detailed information about a specific job match."""
    db = get_supabase_client()

    result = (
        db.table("job_matches")
        .select(
            "*, "
            "job_listings!inner(title, url, location, "
            "company_sources!inner(company_name))"
        )
        .eq("id", match_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    row = result.data[0]

    # Verify this match belongs to the current user
    resume_check = (
        db.table("resumes")
        .select("user_id")
        .eq("id", row["resume_id"])
        .execute()
    )

    if not resume_check.data or resume_check.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    job = row.get("job_listings", {})
    source = job.get("company_sources", {})

    return JobMatchResponse(
        id=row["id"],
        job_id=row["job_id"],
        resume_id=row["resume_id"],
        overall_score=row["overall_score"],
        skills_score=row["skills_score"],
        experience_score=row["experience_score"],
        title_score=row["title_score"],
        location_score=row["location_score"],
        matching_skills=row.get("matching_skills", []),
        missing_skills=row.get("missing_skills", []),
        summary=row.get("summary", ""),
        status=row["status"],
        created_at=row["created_at"],
        job_title=job.get("title"),
        company_name=source.get("company_name"),
        job_url=job.get("url"),
        job_location=job.get("location"),
    )


@router.patch("/{match_id}/status", response_model=JobMatchResponse)
async def update_match_status(
    match_id: str,
    body: MatchStatusUpdate,
    current_user: dict = Depends(require_user),
):
    """Update the status of a job match (e.g., mark as applied)."""
    db = get_supabase_client()

    # Verify ownership first
    match_result = (
        db.table("job_matches")
        .select("resume_id")
        .eq("id", match_id)
        .execute()
    )

    if not match_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")

    resume_check = (
        db.table("resumes")
        .select("user_id")
        .eq("id", match_result.data[0]["resume_id"])
        .execute()
    )

    if not resume_check.data or resume_check.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")

    # Update status
    result = (
        db.table("job_matches")
        .update({"status": body.status.value})
        .eq("id", match_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update status.",
        )

    logger.info(f"Match {match_id} status updated to {body.status.value}")

    # Return full match data
    return await get_match_detail(match_id, current_user)
