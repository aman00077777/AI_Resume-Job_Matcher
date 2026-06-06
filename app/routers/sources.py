"""Company career source management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from app.auth import require_user
from app.database import get_supabase_client
from app.models.schemas import (
    CompanySourceCreate,
    CompanySourceUpdate,
    CompanySourceResponse,
)

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.post("/", response_model=CompanySourceResponse, status_code=status.HTTP_201_CREATED)
async def add_source(
    source: CompanySourceCreate,
    current_user: dict = Depends(require_user),
):
    """Add a new company career page URL to monitor."""
    db = get_supabase_client()

    # Check for duplicate URL
    existing = (
        db.table("company_sources")
        .select("id")
        .eq("user_id", current_user["id"])
        .eq("career_url", source.career_url)
        .execute()
    )

    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This career URL is already being monitored.",
        )

    result = db.table("company_sources").insert({
        "user_id": current_user["id"],
        "company_name": source.company_name,
        "career_url": source.career_url,
    }).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add source.",
        )

    row = result.data[0]
    logger.info(f"Source added: {source.company_name} ({source.career_url})")

    return CompanySourceResponse(
        id=row["id"],
        user_id=row["user_id"],
        company_name=row["company_name"],
        career_url=row["career_url"],
        is_active=row["is_active"],
        last_scraped_at=row.get("last_scraped_at"),
        created_at=row["created_at"],
    )


@router.get("/", response_model=list[CompanySourceResponse])
async def list_sources(current_user: dict = Depends(require_user)):
    """List all company sources for the current user."""
    db = get_supabase_client()

    result = (
        db.table("company_sources")
        .select("*")
        .eq("user_id", current_user["id"])
        .order("created_at", desc=True)
        .execute()
    )

    return [
        CompanySourceResponse(
            id=row["id"],
            user_id=row["user_id"],
            company_name=row["company_name"],
            career_url=row["career_url"],
            is_active=row["is_active"],
            last_scraped_at=row.get("last_scraped_at"),
            created_at=row["created_at"],
        )
        for row in result.data
    ]


@router.patch("/{source_id}", response_model=CompanySourceResponse)
async def update_source(
    source_id: str,
    update: CompanySourceUpdate,
    current_user: dict = Depends(require_user),
):
    """Update a company source (name, URL, or active status)."""
    db = get_supabase_client()

    update_data = update.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update.",
        )

    result = (
        db.table("company_sources")
        .update(update_data)
        .eq("id", source_id)
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )

    row = result.data[0]
    return CompanySourceResponse(
        id=row["id"],
        user_id=row["user_id"],
        company_name=row["company_name"],
        career_url=row["career_url"],
        is_active=row["is_active"],
        last_scraped_at=row.get("last_scraped_at"),
        created_at=row["created_at"],
    )


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    current_user: dict = Depends(require_user),
):
    """Remove a company source and all its associated job listings/matches."""
    db = get_supabase_client()

    result = (
        db.table("company_sources")
        .delete()
        .eq("id", source_id)
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )

    logger.info(f"Source deleted: {source_id}")
