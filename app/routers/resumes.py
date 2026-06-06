"""Resume upload and management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from loguru import logger

from app.auth import require_user
from app.database import get_supabase_client
from app.models.schemas import ResumeResponse
from app.services.resume_parser import parse_resume, ResumeParsingError

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_user),
):
    """Upload a PDF resume, parse it with AI, and store the structured data.

    Accepts a single PDF file. The resume text is extracted with PyPDF2,
    then Claude structures it into skills, experience, education, and
    job titles.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted.",
        )

    # Read file contents
    pdf_bytes = await file.read()

    if len(pdf_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if len(pdf_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit.",
        )

    # Parse the resume
    try:
        parsed = parse_resume(pdf_bytes, filename=file.filename)
    except ResumeParsingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    # Store in Supabase
    db = get_supabase_client()

    try:
        result = db.table("resumes").insert({
            "user_id": current_user["id"],
            **parsed,
        }).execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store resume.",
            )

        resume = result.data[0]
        logger.info(f"Resume stored for user {current_user['id']}: {file.filename}")

        return ResumeResponse(
            id=resume["id"],
            user_id=resume["user_id"],
            filename=resume["filename"],
            skills=resume.get("skills", []),
            experience_years=resume.get("experience_years", 0),
            education=resume.get("education", []),
            job_titles=resume.get("job_titles", []),
            summary=resume.get("summary", ""),
            parsed_at=resume["parsed_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error storing resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store resume data.",
        )


@router.get("/current", response_model=ResumeResponse | None)
async def get_current_resume(current_user: dict = Depends(require_user)):
    """Get the most recently uploaded resume for the current user."""
    db = get_supabase_client()

    result = (
        db.table("resumes")
        .select("*")
        .eq("user_id", current_user["id"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    resume = result.data[0]
    return ResumeResponse(
        id=resume["id"],
        user_id=resume["user_id"],
        filename=resume["filename"],
        skills=resume.get("skills", []),
        experience_years=resume.get("experience_years", 0),
        education=resume.get("education", []),
        job_titles=resume.get("job_titles", []),
        summary=resume.get("summary", ""),
        parsed_at=resume["parsed_at"],
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(resume_id: str, current_user: dict = Depends(require_user)):
    """Delete a specific resume."""
    db = get_supabase_client()

    result = (
        db.table("resumes")
        .delete()
        .eq("id", resume_id)
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )
